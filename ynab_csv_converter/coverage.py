"""Which dates are already imported, and which are missing.

Coverage is the union of date ranges of archived exports. Everything here is pure: dates in, dates out.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import pairwise
from typing import Literal

from .transaction import Transaction

ONE_DAY = timedelta(days=1)


@dataclass(frozen=True, order=True)
class DateRange:
    first: date
    last: date

    def __post_init__(self):
        if self.first > self.last:
            raise ValueError(f"Range starts after it ends: {self.first} > {self.last}")

    @classmethod
    def spanning(cls, dates: Iterable[date]) -> "DateRange":
        dates = list(dates)
        return cls(min(dates), max(dates))

    @property
    def days(self) -> int:
        return (self.last - self.first).days + 1

    def contains(self, other: "DateRange") -> bool:
        return self.first <= other.first and other.last <= self.last

    def overlaps(self, other: "DateRange") -> bool:
        return self.first <= other.last and other.first <= self.last

    def __str__(self) -> str:
        return f"{self.first} to {self.last}"


def span_of(transactions: Iterable[Transaction]) -> DateRange | None:
    dates = [transaction.date for transaction in transactions]
    return DateRange.spanning(dates) if dates else None


def merge(ranges: Iterable[DateRange], max_gap_days: int = 0) -> list[DateRange]:
    """Union of ranges. Overlapping and back-to-back ranges become one.

    With `max_gap_days`, ranges separated by that many missing days or fewer also become one.
    """
    merged: list[DateRange] = []
    for current in sorted(ranges):
        if merged and current.first <= merged[-1].last + timedelta(days=max_gap_days + 1):
            merged[-1] = DateRange(merged[-1].first, max(merged[-1].last, current.last))
        else:
            merged.append(current)
    return merged


def holes(ranges: Iterable[DateRange]) -> list[DateRange]:
    """Missing dates between the earliest and latest covered date."""
    merged = merge(ranges)
    return [DateRange(before.last + ONE_DAY, after.first - ONE_DAY) for before, after in pairwise(merged)]


@dataclass(frozen=True)
class Gap:
    """Dates missing right before or right after a file being imported."""

    missing: DateRange
    side: Literal["before", "after"]

    def __str__(self) -> str:
        before = self.missing.first - ONE_DAY
        after = self.missing.last + ONE_DAY
        if self.side == "before":
            return f"Missing {self.missing}: last import ends {before}, this file starts {after}"
        return f"Missing {self.missing}: this file ends {before}, next import starts {after}"


def batch_gaps(
    spans: Sequence[DateRange], existing: Sequence[DateRange], max_gap_days: int
) -> list[list[Gap]]:
    """Gaps longer than `max_gap_days` next to each file in a batch, in `spans` order.

    Every file in the batch counts as covered, so importing Aug and Sep together is fine.
    A gap between two files of the batch is reported once, on the later file.
    A file whose dates are all covered already adds nothing, so it gets no gaps either.
    """
    existing = merge(existing)
    coverage = merge([*existing, *spans])
    candidates = [
        [] if _is_covered(span, existing) else _adjacent_gaps(span, coverage, max_gap_days) for span in spans
    ]

    latest_owner: dict[DateRange, int] = {}
    for index, gaps in enumerate(candidates):
        for gap in gaps:
            owner = latest_owner.get(gap.missing)
            if owner is None or spans[owner] < spans[index]:
                latest_owner[gap.missing] = index
    return [
        [gap for gap in gaps if latest_owner[gap.missing] == index] for index, gaps in enumerate(candidates)
    ]


def _adjacent_gaps(span: DateRange, coverage: list[DateRange], max_gap_days: int) -> list[Gap]:
    position = next(i for i, block in enumerate(coverage) if block.contains(span))
    block = coverage[position]
    gaps = []
    if position > 0 and block.first == span.first:
        missing = DateRange(coverage[position - 1].last + ONE_DAY, span.first - ONE_DAY)
        gaps.append(Gap(missing, "before"))
    if position + 1 < len(coverage) and block.last == span.last:
        missing = DateRange(span.last + ONE_DAY, coverage[position + 1].first - ONE_DAY)
        gaps.append(Gap(missing, "after"))
    return [gap for gap in gaps if gap.missing.days > max_gap_days]


def is_already_imported(span: DateRange, existing: Sequence[DateRange], new_count: int) -> bool:
    """Nothing new and every date already covered: most likely a file imported before."""
    return new_count == 0 and _is_covered(span, merge(existing))


def count_covered(dates: Iterable[date], existing: Sequence[DateRange]) -> int:
    """How many of `dates` fall inside `existing`."""
    merged = merge(existing)
    return sum(any(block.first <= day <= block.last for block in merged) for day in dates)


def _is_covered(span: DateRange, merged: list[DateRange]) -> bool:
    return any(block.contains(span) for block in merged)
