from datetime import date
from decimal import Decimal

import pytest

from tests.legacy import legacy_transactions
from ynab_csv_converter.providers.hypovereinsbank import provider
from ynab_csv_converter.transaction import Transaction

EXPORT = (
    "Kontonummer;Buchungsdatum;Valuta;Empfaenger 1;Empfaenger 2;Verwendungszweck;Betrag;Waehrung\n"
    '"123456";"03.02.2024";"02.02.2024";"REWE MARKT";"";"KARTENZAHLUNG";"-1.234,50";"EUR"\n'
    '"123456";"04.02.2024";"04.02.2024";"MÜLLER GMBH";"HANS MÜLLER";"LOHN FEBRUAR";"2.500,00";"EUR"\n'
    '"123456";"05.02.2024";"05.02.2024";"";"";"BARGELDAUSZAHLUNG";"-50,00";"EUR"\n'
    '"123456";"06.02.2024";"06.02.2024";"";"ERIKA MUSTERMANN";"UEBERWEISUNG";"-12,34";"EUR"\n'
)


@pytest.fixture
def export(tmp_path):
    path = tmp_path / "export.csv"
    path.write_text(EXPORT, encoding="utf-16-le")
    return path


def test_parses_export(export):
    assert provider.read_transactions(export) == [
        Transaction(date(2024, 2, 3), "Rewe markt", Decimal("-1234.50"), memo="Kartenzahlung"),
        Transaction(
            date(2024, 2, 4),
            "Müller gmbh",
            Decimal("2500.00"),
            memo="Lohn februar Empfänger 2: Hans müller",
        ),
        Transaction(date(2024, 2, 5), "Bargeldauszahlung", Decimal("-50.00")),
        # Leading space is legacy output, kept for dedup against old converted rows.
        Transaction(
            date(2024, 2, 6), "Ueberweisung", Decimal("-12.34"), memo=" Empfänger 2: Erika mustermann"
        ),
    ]


def test_matches_legacy_parser(export):
    assert provider.read_transactions(export) == legacy_transactions("hypovereinsbank", export)
