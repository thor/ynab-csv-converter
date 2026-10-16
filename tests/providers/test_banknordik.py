from datetime import date
from decimal import Decimal

from tests.legacy import legacy_transactions
from ynab_csv_converter.providers.banknordik import provider
from ynab_csv_converter.transaction import Transaction

EXPORT = (
    '"03-02-2024";"02-02-2024";"Føroya Keypsamtøkan";"-1.234,50";"10.000,00";"";""\n'
    '"01-02-2024";"01-02-2024";"Løn";"25.000,00";"11.234,50";"x";"y"\n'
)


def write_export(tmp_path):
    path = tmp_path / "export.csv"
    path.write_text(EXPORT, encoding="utf-8-sig")
    return path


def test_parses_export(tmp_path):
    assert provider.read_transactions(write_export(tmp_path)) == [
        Transaction(date(2024, 2, 3), "Føroya Keypsamtøkan", Decimal("-1234.50")),
        Transaction(date(2024, 2, 1), "Løn", Decimal("25000.00")),
    ]


def test_matches_legacy_parser(tmp_path):
    path = write_export(tmp_path)
    assert provider.read_transactions(path) == legacy_transactions("banknordik", path)
