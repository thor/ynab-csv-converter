from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook

from ynab_csv_converter import ynab_csv
from ynab_csv_converter.convert import (
    ImportBatch,
    SourceError,
    _archive_suffix,
    apply,
    existing_coverage,
    new_transactions,
)
from ynab_csv_converter.coverage import DateRange
from ynab_csv_converter.formula import Formula
from ynab_csv_converter.providers.base import ParseError
from ynab_csv_converter.store import StoreError
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
    assert applied.archived == [formula.archivepath / "spk-20260703-20260701.csv"]
    assert applied.archived[0].exists() and not path.exists()


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
    assert [archived.name for archived in applied.archived] == ["spk-20260701-20260701-1.csv"]


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


def stored(folder: Path, name: str, *transactions: Transaction) -> Path:
    folder.mkdir(exist_ok=True)
    ynab_csv.write(folder / name, transactions)
    return folder / name


def test_coverage_comes_from_the_archive_not_consolidated_files(formula):
    stored(formula.archivepath, "spk-20260703-20260701.csv")
    stored(formula.archivepath, "spk-20260731-20260720.csv")
    stored(formula.outpath, "spk-20260731-20260701.csv", coffee(1), coffee(31))

    assert existing_coverage(formula) == [
        DateRange(date(2026, 7, 1), date(2026, 7, 3)),
        DateRange(date(2026, 7, 20), date(2026, 7, 31)),
    ]


def test_coverage_falls_back_to_converted_files_without_archive(tmp_path, formula):
    stored(formula.outpath, "spk-20260731-20260701.csv", coffee(1), coffee(31))
    path = export(tmp_path / "aug.csv", ("01-08-2026", "Shop", "-10,00"))

    batch = ImportBatch.read(formula, [path])

    assert batch.existing_coverage == [DateRange(date(2026, 7, 1), date(2026, 7, 31))]
    assert not batch.plan(batch.sources[0]).first_import


def test_corrupt_converted_file_outside_the_batch_is_not_read(tmp_path, formula):
    formula.outpath.mkdir()
    (formula.outpath / "spk-20260630-20260601.csv").write_text("garbage,row\n1,2\n")
    path = export(tmp_path / "july.csv", ("01-07-2026", "Shop", "-10,00"))

    batch = ImportBatch.read(formula, [path])

    assert len(batch.plan(batch.sources[0]).new) == 1


def test_corrupt_converted_file_inside_the_batch_is_an_error(tmp_path, formula):
    formula.outpath.mkdir()
    (formula.outpath / "spk-20260731-20260701.csv").write_text("garbage,row\n1,2\n")
    path = export(tmp_path / "july.csv", ("15-07-2026", "Shop", "-10,00"))

    with pytest.raises(StoreError, match=r"spk-20260731-20260701\.csv: not a valid YNAB CSV"):
        ImportBatch.read(formula, [path])


def test_counts_new_rows_on_dates_already_imported(tmp_path, formula):
    stored(formula.archivepath, "spk-20260731-20260701.csv")
    stored(
        formula.outpath,
        "spk-20260731-20260701.csv",
        Transaction(date(2026, 7, 30), "Shop", Decimal("-10.00")),
    )
    path = export(
        tmp_path / "aug.csv",
        ("30-07-2026", "SHOP 1234", "-10,00"),  # same row, text changed by the bank
        ("31-07-2026", "Late", "-1,00"),
        ("01-08-2026", "Bus", "-3,00"),
    )
    batch = ImportBatch.read(formula, [path])

    plan = batch.plan(batch.sources[0])

    assert len(plan.new) == 3
    assert plan.new_on_imported_dates == 2
    assert not plan.already_imported


def test_archive_drops_a_suffix_the_store_cannot_read():
    assert _archive_suffix(Path("export.xlsx")) == ".xlsx"
    assert _archive_suffix(Path("export.csv~")) == ""
    assert _archive_suffix(Path("export")) == ""


def test_xlsx_is_saved_as_csv_and_archived_next_to_the_original(tmp_path):
    formula = Formula(
        path=tmp_path / "formula.yml",
        format="banknorwegian",
        outpath=tmp_path / "out",
        archivepath=tmp_path / "archive",
        outprefix="bn",
    )
    header = [
        "TransactionDate",
        "Text",
        "Type",
        "Currency Amount",
        "Currency Rate",
        "Currency",
        "Amount",
        "Merchant Area",
        "Merchant Category",
        "BookDate",
        "ValueDate",
    ]
    rows = [
        [
            datetime(2025, 9, 1),
            "REMA 1000",
            "Kjøp",
            -40.0,
            1,
            "NOK",
            -40.0,
            "Oslo",
            "GROCERY",
            datetime(2025, 9, 2),
            None,
        ],
        [
            datetime(2025, 9, 3),
            "CAFE",
            "Kjøp",
            -12.5,
            13.97075,
            "GBP",
            -174.63,
            "Leeds",
            "FOOD",
            datetime(2025, 9, 4),
            None,
        ],
    ]
    workbook = Workbook()
    for row in [header, *rows]:
        workbook.active.append(row)
    path = tmp_path / "kontoutskrift.xlsx"
    workbook.save(path)

    batch = ImportBatch.read(formula, [path])
    source = batch.sources[0]

    assert source.saved_as_csv.decode("utf-8-sig").splitlines()[1:] == [
        "2025/09/01,REMA 1000,Kjøp,-40,1,NOK,-40,Oslo,GROCERY,2025/09/02,",
        "2025/09/03,CAFE,Kjøp,-12.5,13.97075,GBP,-174.63,Leeds,FOOD,2025/09/04,",
    ]
    assert [(t.amount, t.memo) for t in source.transactions] == [
        (Decimal("-40"), "GROCERY"),
        (Decimal("-174.63"), "FOOD -12.5 GBP"),
    ]

    formula.outpath.mkdir()
    applied = apply(formula, batch.plan(source))

    assert [archived.name for archived in applied.archived] == [
        "bn-20250903-20250901.csv",
        "bn-20250903-20250901.xlsx",
    ]
    assert applied.archived[0].read_bytes() == source.saved_as_csv
    assert not path.exists()


def test_xlsx_parse_error_names_the_workbook(tmp_path):
    formula = Formula(tmp_path / "f.yml", "banknorwegian", tmp_path / "out", tmp_path / "archive", "bn")
    workbook = Workbook()
    workbook.active.append(["TransactionDate"])
    workbook.active.append(["not a date", "x"])
    path = tmp_path / "bad.xlsx"
    workbook.save(path)

    with pytest.raises(ParseError, match=r"bad\.xlsx:2: "):
        ImportBatch.read(formula, [path])
