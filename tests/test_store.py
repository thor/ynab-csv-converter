import re
from datetime import date

import pytest

from ynab_csv_converter.coverage import DateRange
from ynab_csv_converter.store import StoreError, converted_files, free_path, list_files, read_converted

JULY = DateRange(date(2026, 7, 1), date(2026, 7, 31))


def touch(folder, *names):
    folder.mkdir(exist_ok=True)
    for name in names:
        (folder / name).write_text("")


def test_free_path_puts_newest_date_first_and_counts_up(tmp_path):
    first = free_path(tmp_path, "spk", JULY, ".csv")
    assert first.name == "spk-20260731-20260701.csv"

    first.write_text("")
    second = free_path(tmp_path, "spk", JULY, ".csv")
    assert second.name == "spk-20260731-20260701-1.csv"

    second.write_text("")
    assert free_path(tmp_path, "spk", JULY, ".csv").name == "spk-20260731-20260701-2.csv"


def test_free_path_keeps_any_suffix(tmp_path):
    assert free_path(tmp_path, "spk", JULY, ".xlsx").name == "spk-20260731-20260701.xlsx"
    assert free_path(tmp_path, "spk", JULY, "").name == "spk-20260731-20260701"


def test_lists_legacy_and_new_names_oldest_first(tmp_path):
    touch(
        tmp_path,
        "spk-20260831-20260801.xlsx",
        "spk-20260731-20260701.csv",
        "spk-20260731-20260701-1.csv",
        "spk-20260630-20260601",
    )

    found = list_files(tmp_path, "spk")

    assert [stored.path.name for stored in found] == [
        "spk-20260630-20260601",
        "spk-20260731-20260701-1.csv",
        "spk-20260731-20260701.csv",
        "spk-20260831-20260801.xlsx",
    ]
    assert found[0].span == DateRange(date(2026, 6, 1), date(2026, 6, 30))


def test_ignores_unrelated_files(tmp_path):
    touch(
        tmp_path,
        "notes.txt",
        "spk-latest.csv",
        "spk-20261399-20261301.csv",  # no such date
        "spk-20260701-20260731.csv",  # range backwards
        "spk-euro-20260731-20260701.csv",  # other prefix
        ".spk-20260731-20260701.csv.tmp",
    )
    (tmp_path / "spk-20260831-20260801.csv").mkdir()

    assert list_files(tmp_path, "spk") == []


@pytest.mark.parametrize(
    "name",
    ["spk-20260731-20260701 copy.csv", "spk-20260731-20260701 (1).csv", "spk-20260731-20260701.csv.bak"],
)
def test_lookalike_name_is_an_error(tmp_path, name):
    # Skipping it would drop its rows from the dedup baseline.
    touch(tmp_path, "spk-20260630-20260601.csv", name)

    with pytest.raises(StoreError, match=rf"{re.escape(name)}: .* Rename or remove it"):
        list_files(tmp_path, "spk")


def test_converted_files_are_csv_only(tmp_path):
    touch(tmp_path, "spk-20260731-20260701.csv", "spk-20260831-20260801.xlsx", "spk-20260930-20260901.CSV")

    assert [stored.path.name for stored in converted_files(tmp_path, "spk")] == [
        "spk-20260731-20260701.csv",
        "spk-20260930-20260901.CSV",
    ]


def test_missing_folder_has_no_files(tmp_path):
    assert list_files(tmp_path / "nope", "spk") == []


def test_read_converted_names_the_file_on_bad_content(tmp_path):
    path = tmp_path / "spk-20260731-20260701.csv"
    path.write_text("Date,Payee,Category,Memo,Outflow,Inflow\n01/07/2026,Shop,,,abc,0.00\n")

    with pytest.raises(StoreError, match=r"spk-20260731-20260701\.csv: not a valid YNAB CSV"):
        read_converted(path)
