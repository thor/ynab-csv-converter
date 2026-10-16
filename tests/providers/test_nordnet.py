from datetime import date
from decimal import Decimal

from ynab_csv_converter.providers.nordnet import provider
from ynab_csv_converter.transaction import Transaction

HEADER = "\t".join(f"column {number}" for number in range(27))


def nordnet_row(
    booking_date,
    transaction_type,
    security,
    instrument_type,
    quantity,
    price,
    amount,
    currency,
    exchange_rate,
):
    cells = [
        "123456789", booking_date, booking_date, booking_date, "12345",
        transaction_type, security, instrument_type, "US0378331005", quantity, price,
        "0", "0", "DKK", amount, currency,
        "0", "0", "10", "1 000,00", exchange_rate, "",
        "", "", "12345678", "", "",
    ]  # fmt: skip
    return "\t".join(cells)


ROWS = [
    nordnet_row("2024-03-05", "KØBT", "AAPL", "Aktie", "10", "123,45", "-8 234,57", "USD", "6,6812"),
    "",  # exports contain blank lines
    nordnet_row("2024-03-04", "SOLGT", "NOVO B", "Aktie", "4", "250,00", "1 000,00", "DKK", "0"),
    nordnet_row("2024-03-03", "KØBT", "SAP", "Aktier", "2", "1,10", "-10,00", "EUR", "3"),
    nordnet_row("2024-03-02", "INDBETALING", "", "", "0", "0", "1 234,56", "EUR", "0"),
    nordnet_row("2024-03-01", "RENTE", "", "", "0", "0", "-12,34", "NOK", "0"),
]
EXPORT = "\n".join([HEADER, *ROWS]) + "\n"


def write_export(tmp_path, content=EXPORT):
    path = tmp_path / "export.csv"
    path.write_text(content, encoding="utf-16")
    return path


def test_parses_export(tmp_path):
    assert provider.read_transactions(write_export(tmp_path)) == [
        Transaction(
            date(2024, 3, 5),
            "Købt AAPL",
            Decimal("-55006.93"),
            memo="10 stk. til USD 824.79414 (veksl. 6,6812)",
        ),
        Transaction(date(2024, 3, 4), "Solgt NOVO B", Decimal("1000.00"), memo="4 stk. til DKK 0.0"),
        Transaction(
            date(2024, 3, 3),
            "Købt SAP",
            Decimal("-74.60"),
            memo="2 stk. til EUR 3.3000000000000003 (veksl. 3)",
        ),
        Transaction(date(2024, 3, 2), "Indbetaling", Decimal("9209.82")),
        Transaction(date(2024, 3, 1), "Rente", Decimal("-12.34")),
    ]


def test_accepts_no_break_space_thousands(tmp_path):
    rows = [
        nordnet_row("2024-03-02", "INDBETALING", "", "", "0", "0", "1\xa0234,56", "DKK", "0"),
        nordnet_row("2024-03-01", "INDBETALING", "", "", "0", "0", "1 000,00", "DKK", "0"),
    ]
    path = write_export(tmp_path, "\n".join([HEADER, *rows]) + "\n")

    assert [transaction.amount for transaction in provider.read_transactions(path)] == [
        Decimal("1234.56"),
        Decimal("1000.00"),
    ]
