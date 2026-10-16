from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ynab_csv_converter import ynab_csv
from ynab_csv_converter.consolidate import consolidate, plan_consolidation
from ynab_csv_converter.formula import Formula
from ynab_csv_converter.transaction import Transaction


@pytest.fixture
def formula(tmp_path) -> Formula:
    (tmp_path / "out").mkdir()
    return Formula(
        path=tmp_path / "formula.yml",
        format="sparekassen",
        outpath=tmp_path / "out",
        archivepath=tmp_path / "archive",
        outprefix="spk",
    )


def shop(day: int) -> Transaction:
    return Transaction(date(2026, 7, day), f"Shop {day}", Decimal("-1.00"))


def names(folder: Path) -> list[str]:
    return sorted(path.name for path in folder.iterdir())


def test_merged_file_may_take_the_name_of_an_original(formula):
    # The first file already spans everything, so the merge lands on its name.
    ynab_csv.write(formula.outpath / "spk-20260731-20260701.csv", [shop(1), shop(31)])
    ynab_csv.write(formula.outpath / "spk-20260715-20260710.csv", [shop(10), shop(15)])

    merged = consolidate(formula, plan_consolidation(formula))

    assert merged == formula.outpath / "spk-20260731-20260701.csv"
    assert names(formula.outpath) == ["spk-20260731-20260701.csv"]
    assert ynab_csv.read(merged) == [shop(1), shop(10), shop(15), shop(31)]


def test_merged_file_does_not_overwrite_a_file_it_did_not_read(formula):
    ynab_csv.write(formula.outpath / "spk-20260710-20260701.csv", [shop(1), shop(10)])
    ynab_csv.write(formula.outpath / "spk-20260731-20260720.csv", [shop(20), shop(31)])
    plan = plan_consolidation(formula)
    stranger = formula.outpath / "spk-20260731-20260701.csv"
    ynab_csv.write(stranger, [shop(5)])

    merged = consolidate(formula, plan)

    assert merged == formula.outpath / "spk-20260731-20260701-1.csv"
    assert ynab_csv.read(stranger) == [shop(5)]


def test_all_empty_files_are_removed(formula):
    ynab_csv.write(formula.outpath / "spk-20260710-20260701.csv", [])
    ynab_csv.write(formula.outpath / "spk-20260731-20260720.csv", [])

    assert consolidate(formula, plan_consolidation(formula)) is None
    assert names(formula.outpath) == []


def test_failed_write_keeps_the_originals_and_no_temp_file(formula, monkeypatch):
    ynab_csv.write(formula.outpath / "spk-20260710-20260701.csv", [shop(1)])
    ynab_csv.write(formula.outpath / "spk-20260731-20260720.csv", [shop(31)])
    before = names(formula.outpath)

    def fail(path, transactions):
        path.write_text("partial")
        raise OSError("disk full")

    monkeypatch.setattr(ynab_csv, "write", fail)

    with pytest.raises(OSError, match="disk full"):
        consolidate(formula, plan_consolidation(formula))
    assert names(formula.outpath) == before
