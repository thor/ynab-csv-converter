from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ynab_csv_converter import ynab_csv
from ynab_csv_converter.convert import ImportBatch, SourceError, apply, new_transactions
from ynab_csv_converter.formula import Formula
from ynab_csv_converter.transaction import Transaction


def coffee(day: int = 1, amount: str = "-35.00") -> Transaction:
    return Transaction(date(2026, 7, day), "Coffee", Decimal(amount))


def test_new_transactions_counts_identical_rows():
    assert new_transactions([coffee(), coffee()], [coffee()]) == [coffee()]
    assert new_transactions([coffee(), coffee()], [coffee(), coffee()]) == []
    assert new_transactions([coffee()], [coffee(), coffee()]) == []


def test_new_transactions_ignores_converted_rows_outside_the_range():
    # A converted row on another day is not evidence this row was imported.
    assert new_transactions([coffee(2)], [coffee(1)]) == [coffee(2)]


def test_new_transactions_compares_amounts_by_value():
    assert new_transactions([coffee(amount="-35.0")], [coffee(amount="-35.00")]) == []


@pytest.fixture
def formula(tmp_path) -> Formula:
    return Formula(
        path=tmp_path / "formula.yml",
        format="sparekassen",
        outpath=tmp_path / "out",
        archivepath=tmp_path / "archive",
        outprefix="spk",
    )


def export(path: Path, *rows: tuple[str, str, str]) -> Path:
    """Sparekassen rows as (dd-mm-yyyy, text, amount)."""
    lines = [f'"{day}";"{day}";"{text}";"{amount}";"0,00"' for day, text, amount in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    return path


def test_applies_factor(tmp_path, formula):
    formula = Formula(**{**formula.__dict__, "factor": Decimal("7.45")})
    path = export(tmp_path / "a.csv", ("01-07-2026", "Shop", "-10,00"))

    [source] = ImportBatch.read(formula, [path]).sources

    assert source.transactions == [Transaction(date(2026, 7, 1), "Shop", Decimal("-74.50"))]


def test_batch_dedups_overlapping_files_against_each_other(tmp_path, formula):
    first = export(tmp_path / "a.csv", ("01-07-2026", "Shop", "-10,00"), ("02-07-2026", "Bar", "-5,00"))
    second = export(tmp_path / "b.csv", ("02-07-2026", "Bar", "-5,00"), ("03-07-2026", "Bus", "-3,00"))
    batch = ImportBatch.read(formula, [second, first])

    assert [source.path.name for source in batch.sources] == ["a.csv", "b.csv"]
    first_plan = batch.plan(batch.sources[0])
    assert len(first_plan.new) == 2
    assert first_plan.first_import
    batch.record(first_plan)

    second_plan = batch.plan(batch.sources[1])
    assert [t.payee for t in second_plan.new] == ["Bus"]
    assert second_plan.duplicate_count == 1
    assert not second_plan.first_import


def test_apply_writes_new_rows_and_archives_with_full_range(tmp_path, formula):
    (formula.outpath).mkdir()
    old = Transaction(date(2026, 7, 1), "Shop", Decimal("-10.00"))
    ynab_csv.write(formula.outpath / "spk-20260701-20260701.csv", [old])
    path = export(tmp_path / "july.csv", ("03-07-2026", "Bus", "-3,00"), ("01-07-2026", "Shop", "-10,00"))
    batch = ImportBatch.read(formula, [path])

    plan = batch.plan(batch.sources[0])
    applied = apply(formula, plan)

    assert applied.converted == formula.outpath / "spk-20260703-20260703.csv"
    assert ynab_csv.read(applied.converted) == [Transaction(date(2026, 7, 3), "Bus", Decimal("-3.00"))]
    assert applied.archived == formula.archivepath / "spk-20260703-20260701.csv"
    assert applied.archived.exists() and not path.exists()


def test_apply_archives_even_when_nothing_is_new(tmp_path, formula):
    path = export(tmp_path / "july.csv", ("01-07-2026", "Shop", "-10,00"))
    batch = ImportBatch.read(formula, [path])
    apply(formula, batch.plan(batch.sources[0]))
    path = export(tmp_path / "july.csv", ("01-07-2026", "Shop", "-10,00"))

    batch = ImportBatch.read(formula, [path])
    plan = batch.plan(batch.sources[0])
    applied = apply(formula, plan)

    assert plan.already_imported
    assert applied.converted is None
    assert applied.archived.name == "spk-20260701-20260701-1.csv"


def test_same_path_twice_is_read_once(tmp_path, formula):
    path = export(tmp_path / "july.csv", ("01-07-2026", "Shop", "-10,00"))

    assert len(ImportBatch.read(formula, [path, tmp_path / "." / "july.csv"]).sources) == 1


def test_missing_source(tmp_path, formula):
    with pytest.raises(SourceError, match="nope.csv: file not found"):
        ImportBatch.read(formula, [tmp_path / "nope.csv"])


def test_undecodable_source_names_the_file(tmp_path, formula):
    path = tmp_path / "binary.csv"
    path.write_bytes(b"\xff\xfe\x00garbage")

    with pytest.raises(SourceError, match="binary.csv: "):
        ImportBatch.read(formula, [path])
