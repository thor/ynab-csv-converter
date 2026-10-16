from datetime import date
from decimal import Decimal

from tests.legacy import legacy_transactions
from ynab_csv_converter.providers.banknorwegian import provider
from ynab_csv_converter.transaction import Transaction

EXPORT = (
    "TransactionDate,Text,Type,Currency Amount,Currency Rate,Currency,Amount,Merchant Area,Merchant Category,"
    "BookDate,ValueDate\n"
    "2024/03/01,REMA 1000,Varekjøp,-245.50,1,NOK,-245.50,OSLO,Grocery Stores,2024/03/02,2024/03/02\n"
    "2024/03/02,CAFE PARIS,Varekjøp,-12.50,11.52,EUR,-144.00,PARIS,Restaurants,2024/03/04,2024/03/04\n"
    "2024/03/05,Innbetaling,Betaling,1000.00,1,NOK,1000.00,,,2024/03/05,2024/03/05\n"
    "2024/03/06,AMAZON REFUND,Retur,5.00,10.80,USD,54.00,SEATTLE,Book Stores,2024/03/07,2024/03/07\n"
    "2024/03/07,Rente,Rente,,,,-12.34,,,2024/03/07,2024/03/07\n"
)


def write_export(tmp_path):
    path = tmp_path / "banknorwegian.csv"
    path.write_text(EXPORT, encoding="utf-8-sig")
    return path


def test_parses_export(tmp_path):
    assert provider.read_transactions(write_export(tmp_path)) == [
        Transaction(date(2024, 3, 1), "REMA 1000", Decimal("-245.50"), memo="Grocery Stores"),
        Transaction(date(2024, 3, 2), "CAFE PARIS", Decimal("-144.00"), memo="Restaurants -12.50 EUR"),
        Transaction(date(2024, 3, 5), "Innbetaling", Decimal("1000.00")),
        # Legacy quirks kept for dedup stability: leading space, and blank currency counts as foreign.
        Transaction(date(2024, 3, 6), "AMAZON REFUND", Decimal("54.00"), memo=" 5.00 USD"),
        Transaction(date(2024, 3, 7), "Rente", Decimal("-12.34"), memo="  "),
    ]


def test_matches_legacy_parser(tmp_path):
    path = write_export(tmp_path)
    assert provider.read_transactions(path) == legacy_transactions("banknorwegian", path)
