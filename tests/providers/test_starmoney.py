from datetime import date
from decimal import Decimal

import pytest

from ynab_csv_converter.providers.base import ParseError
from ynab_csv_converter.providers.starmoney import provider
from ynab_csv_converter.transaction import Transaction


def _row(date, payee, memo, amount):
    """A StarMoney row: 20 cells, most of them split and tax columns we ignore."""
    cells = [date, "005", payee, memo, *[""] * 14, amount, "1.000,00 EUR"]
    return ";".join(f'"{cell}"' for cell in cells) + "\n"


EXPORT = (
    ";".join(f"Spalte {n}" for n in range(20))
    + "\n"
    + _row("03.02.2024", "rewe markt gmbh", "KARTENZAHLUNG FILIALE 12", "-1.234,56 EUR")
    + _row("04.02.2024", "ARBEITGEBER AG", "LOHN", "2.500,00 EUR")
    + _row("05.02.2024", "bäckerei", "", "-3,20 EUR")
)


@pytest.fixture
def export(tmp_path):
    path = tmp_path / "export.csv"
    path.write_text(EXPORT, encoding="utf-8")
    return path


def test_parses_export(export):
    assert provider.read_transactions(export) == [
        Transaction(
            date(2024, 2, 3), "Rewe Markt Gmbh", Decimal("-1234.56"), memo="Kartenzahlung filiale 12"
        ),
        Transaction(date(2024, 2, 4), "Arbeitgeber Ag", Decimal("2500.00"), memo="Lohn"),
        Transaction(date(2024, 2, 5), "Bäckerei", Decimal("-3.20")),
    ]


def test_rejects_extra_column(tmp_path):
    """A trailing delimiter would otherwise shift the balance into the amount."""
    path = tmp_path / "export.csv"
    path.write_text(
        EXPORT.splitlines()[0] + "\n" + _row("03.02.2024", "x", "y", "-1,00 EUR").rstrip("\n") + ";\n"
    )

    with pytest.raises(ParseError, match="Expected 20 columns, got 21"):
        provider.read_transactions(path)
