import locale
from datetime import date, datetime
from decimal import Decimal

from openpyxl import Workbook

from ynab_csv_converter.providers.saxotradergo import parse_value_date, provider
from ynab_csv_converter.transaction import Transaction

HEADER = ["Account ID", "Posting Date", "Value Date", "Product", "Net Change", "Cash Balance"]
EXPORT = (
    ",".join(HEADER) + "\n"
    "123456INET,14-10-2024,15-10-2024,Cash dividend 123456789,12.5,1012.50\n"
    "123456INET,01-may-2024,02-may-2024,Custody fee,-3.75,1000.00\n"
    '123456INET,01-jan-2024,01-jan-2024,"Deposit, bank",1000,1003.75\n'
)
EXPECTED = [
    Transaction(
        date(2024, 10, 15),
        "Cash dividend",
        Decimal("12.5"),
        memo="Cash dividend txn #123456789",
    ),
    Transaction(date(2024, 5, 2), "Custody fee", Decimal("-3.75")),
    Transaction(date(2024, 1, 1), "Deposit, bank", Decimal("1000")),
]


def write_csv(tmp_path):
    path = tmp_path / "export.csv"
    path.write_text(EXPORT, encoding="utf-8")
    return path


def test_parses_csv_export(tmp_path):
    assert provider.read_transactions(write_csv(tmp_path)) == EXPECTED


def test_parses_xlsx_export(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(HEADER)
    sheet.append(
        [
            "123456INET",
            datetime(2024, 10, 14),
            datetime(2024, 10, 15),
            "Cash dividend 123456789",
            12.5,
            1012.5,
        ]
    )
    sheet.append(["123456INET", datetime(2024, 5, 1), datetime(2024, 5, 2), "Custody fee", -3.75, 1000])
    sheet.append(["123456INET", "01-jan-2024", "01-jan-2024", "Deposit, bank", 1000, 1003.75])
    path = tmp_path / "export.xlsx"
    workbook.save(path)

    assert provider.read_transactions(path) == EXPECTED


def test_month_names_do_not_depend_on_locale():
    saved_locale = locale.setlocale(locale.LC_TIME)
    try:
        locale.setlocale(locale.LC_TIME, "da_DK.UTF-8")  # Danish: "okt", "maj"
        assert parse_value_date("15-oct-2024") == date(2024, 10, 15)
        assert parse_value_date("05-May-2024") == date(2024, 5, 5)
        assert parse_value_date("05-05-2024") == date(2024, 5, 5)
    finally:
        locale.setlocale(locale.LC_TIME, saved_locale)
