from datetime import date
from decimal import Decimal

import pytest
from openpyxl import Workbook

from ynab_csv_converter import ynab_csv
from ynab_csv_converter.parsing import parse_amount
from ynab_csv_converter.providers.base import ParseError, Provider
from ynab_csv_converter.providers.sources import by_suffix, csv_source, xlsx_source
from ynab_csv_converter.transaction import Transaction


@pytest.mark.parametrize(
    ("text", "marks", "expected"),
    [
        ("-1.234,56", {"decimal_mark": ",", "thousands_mark": "."}, "-1234.56"),
        ("1 234,5", {"decimal_mark": ",", "thousands_mark": " "}, "1234.5"),
        ("12.30", {"decimal_mark": "."}, "12.30"),
        ("−42,00", {"decimal_mark": ","}, "-42.00"),
    ],
)
def test_parse_amount(text, marks, expected):
    assert parse_amount(text, **marks) == Decimal(expected)


@pytest.mark.parametrize("text", ["", "NaN", "1e5", "abc"])
def test_parse_amount_rejects_garbage(text):
    with pytest.raises(ValueError):
        parse_amount(text, decimal_mark=",")


def test_ynab_csv_round_trip(tmp_path):
    transactions = [
        Transaction(date(2024, 1, 31), "Shop, Inc", Decimal("-10.50"), memo="memo"),
        Transaction(date(2024, 2, 1), "Salary", Decimal("100.00"), category="Inflow"),
    ]
    path = tmp_path / "out.csv"
    ynab_csv.write(path, transactions)

    assert path.read_text().splitlines()[1] == '31/01/2024,"Shop, Inc",,memo,10.50,0.00'
    assert ynab_csv.read(path) == transactions


def _first_cell_as_amount(row):
    return Transaction(date(2024, 1, 1), "x", Decimal(str(row[0])))


def test_provider_reads_csv_and_xlsx_alike(tmp_path):
    csv_path = tmp_path / "export.csv"
    csv_path.write_text("Amount\n1.5\n\n2\n")
    xlsx_path = tmp_path / "export.xlsx"
    workbook = Workbook()
    for row in [["Amount"], [1.5], [None], [2]]:
        workbook.active.append(row)
    workbook.save(xlsx_path)

    provider = Provider(
        key="test",
        name="Test",
        read_rows=by_suffix({".csv": csv_source(skip_rows=1), ".xlsx": xlsx_source(skip_rows=1)}),
        parse_row=_first_cell_as_amount,
    )

    amounts = [Decimal("1.5"), Decimal("2")]
    assert [t.amount for t in provider.read_transactions(csv_path)] == amounts
    assert [t.amount for t in provider.read_transactions(xlsx_path)] == amounts


def test_parse_error_names_file_and_line(tmp_path):
    path = tmp_path / "export.csv"
    path.write_text("1\nnot a number\n")
    provider = Provider("test", "Test", csv_source(), _first_cell_as_amount)

    with pytest.raises(ParseError, match=r"export\.csv:2: could not parse row \['not a number'\]"):
        provider.read_transactions(path)
