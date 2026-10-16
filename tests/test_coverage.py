import calendar
from datetime import date
from decimal import Decimal

import pytest

from ynab_csv_converter.coverage import (
    DateRange,
    Gap,
    batch_gaps,
    count_covered,
    holes,
    is_already_imported,
    merge,
    span_of,
)
from ynab_csv_converter.transaction import Transaction


def span(first: str, last: str) -> DateRange:
    return DateRange(date.fromisoformat(first), date.fromisoformat(last))


def month(number: int, year: int = 2026) -> DateRange:
    return DateRange(date(year, number, 1), date(year, number, calendar.monthrange(year, number)[1]))


def gap_texts(spans, existing, max_gap_days=7):
    return [[str(gap) for gap in gaps] for gaps in batch_gaps(spans, existing, max_gap_days)]


def test_range_rejects_backwards_dates():
    with pytest.raises(ValueError):
        span("2026-07-02", "2026-07-01")


def test_merge_joins_overlapping_and_adjacent_ranges():
    ranges = [month(9), span("2026-07-15", "2026-08-10"), month(7), span("2026-08-11", "2026-08-20")]

    assert merge(ranges) == [span("2026-07-01", "2026-08-20"), month(9)]


def test_merge_keeps_one_day_hole():
    assert merge([span("2026-07-01", "2026-07-10"), span("2026-07-12", "2026-07-20")]) == [
        span("2026-07-01", "2026-07-10"),
        span("2026-07-12", "2026-07-20"),
    ]


def test_merge_bridges_holes_up_to_max_gap_days():
    ranges = [
        span("2026-07-01", "2026-07-10"),
        span("2026-07-13", "2026-07-20"),
        span("2026-07-29", "2026-07-31"),
    ]

    assert merge(ranges, max_gap_days=2) == [
        span("2026-07-01", "2026-07-20"),
        span("2026-07-29", "2026-07-31"),
    ]


def test_holes():
    assert holes([month(1), month(3), month(6)]) == [month(2), span("2026-04-01", "2026-05-31")]
    assert holes([]) == []


def test_later_month_leaves_gap():
    assert gap_texts([month(9)], [month(7)]) == [
        ["Missing 2026-08-01 to 2026-08-31: last import ends 2026-07-31, this file starts 2026-09-01"]
    ]


def test_next_month_has_no_gap():
    assert gap_texts([month(8)], [month(7)]) == [[]]


def test_backfill_leaves_gap_after_file():
    assert gap_texts([month(6)], [month(9)]) == [
        ["Missing 2026-07-01 to 2026-08-31: this file ends 2026-06-30, next import starts 2026-09-01"]
    ]


@pytest.mark.parametrize(
    ("file_starts", "expected_gaps"),
    [
        ("2026-08-01", 0),  # back to back
        ("2026-08-03", 0),  # 2 days missing
        ("2026-08-08", 0),  # 7 days missing: at the limit
        ("2026-08-09", 1),  # 8 days missing
    ],
)
def test_threshold(file_starts, expected_gaps):
    file_span = span(file_starts, "2026-08-31")

    assert len(batch_gaps([file_span], [month(7)], max_gap_days=7)[0]) == expected_gaps


def test_zero_tolerance():
    assert batch_gaps([span("2026-08-02", "2026-08-31")], [month(7)], max_gap_days=0) == [
        [Gap(span("2026-08-01", "2026-08-01"), "before")]
    ]


def test_batch_files_cover_each_other():
    assert gap_texts([month(8), month(9)], [month(7)]) == [[], []]


def test_batch_backfill_before_existing_coverage():
    assert gap_texts([month(7), month(8)], [month(9)]) == [[], []]


def test_gap_between_batch_files_is_reported_once_on_the_later_file():
    assert gap_texts([month(7), month(9)], [month(6)]) == [
        [],
        ["Missing 2026-08-01 to 2026-08-31: last import ends 2026-07-31, this file starts 2026-09-01"],
    ]


def test_gap_reported_once_even_when_spans_given_newest_first():
    gaps = batch_gaps([month(9), month(7)], [month(6)], 7)

    assert gaps == [[Gap(month(8), "before")], []]


def test_file_partly_filling_a_hole_warns_about_the_rest():
    assert gap_texts([span("2026-02-15", "2026-02-28")], [month(1), month(3)]) == [
        ["Missing 2026-02-01 to 2026-02-14: last import ends 2026-01-31, this file starts 2026-02-15"]
    ]


def test_file_in_middle_of_a_hole_warns_on_both_sides():
    gaps = batch_gaps([span("2026-02-10", "2026-02-20")], [month(1), month(3)], 7)

    assert gaps == [
        [Gap(span("2026-02-01", "2026-02-09"), "before"), Gap(span("2026-02-21", "2026-02-28"), "after")]
    ]


def test_file_overlapping_coverage_and_extending_it_has_no_gap():
    assert gap_texts([span("2026-07-20", "2026-08-31")], [month(7)]) == [[]]


def test_already_covered_file_gets_no_gap_even_next_to_an_old_hole():
    assert gap_texts([month(3)], [month(1), month(3)]) == [[]]


def test_first_import_has_no_gaps():
    assert gap_texts([month(7)], []) == [[]]


def test_first_import_of_two_months_with_a_hole():
    assert gap_texts([month(7), month(9)], []) == [
        [],
        ["Missing 2026-08-01 to 2026-08-31: last import ends 2026-07-31, this file starts 2026-09-01"],
    ]


def test_already_imported():
    assert is_already_imported(month(7), [month(6), month(7)], new_count=0)
    assert is_already_imported(span("2026-06-20", "2026-07-10"), [month(6), month(7)], new_count=0)
    assert not is_already_imported(month(7), [month(7)], new_count=1)
    assert not is_already_imported(month(8), [month(7)], new_count=0)
    assert not is_already_imported(month(7), [], new_count=0)


def test_span_of():
    rows = [Transaction(date(2026, 7, day), "Shop", Decimal(-1)) for day in (9, 3, 5)]

    assert span_of(rows) == span("2026-07-03", "2026-07-09")
    assert span_of([]) is None


def test_overlaps():
    assert month(7).overlaps(span("2026-07-31", "2026-08-02"))
    assert span("2026-06-20", "2026-08-02").overlaps(month(7))
    assert not month(7).overlaps(month(8))


def test_count_covered():
    days = [date(2026, 7, 31), date(2026, 8, 1), date(2026, 9, 2)]

    assert count_covered(days, [month(7), month(9)]) == 2
    assert count_covered(days, []) == 0
