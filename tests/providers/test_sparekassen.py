from datetime import date
from decimal import Decimal

from ynab_csv_converter.providers.sparekassen import provider
from ynab_csv_converter.transaction import Transaction

EXPORT = (
    '"03-02-2024";"02-02-2024";"Netto";"-1.234,50";"10.000,00"\n'
    '"01-02-2024";"01-02-2024";"Løn";"25.000,00";"11.234,50"\n'
)


def test_parses_export(tmp_path):
    path = tmp_path / "export.csv"
    path.write_text(EXPORT, encoding="utf-8-sig")

    assert provider.read_transactions(path) == [
        Transaction(date(2024, 2, 3), "Netto", Decimal("-1234.50")),
        Transaction(date(2024, 2, 1), "Løn", Decimal("25000.00")),
    ]
