from datetime import date
from decimal import Decimal

import pytest

from tests.legacy import legacy_transactions
from ynab_csv_converter.providers.americanexpress import provider
from ynab_csv_converter.transaction import Transaction

EXPORT = (
    "Datum,Beschreibung,Karteninhaber,Konto #,Betrag\n"
    '03/02/2024,AMAZON EU SARL  LUXEMBOURG,MAX MUSTERMANN,-12345,"12,50"\n'
    '04/02/2024,ZAHLUNG ERHALTEN,MAX MUSTERMANN,-12345,"-500,00"\n'
    '05/02/2024,SHELL TANKSTELLE,erika mustermann,-12345,"1234,56"\n'
)


@pytest.fixture
def export(tmp_path):
    path = tmp_path / "export.csv"
    path.write_text(EXPORT, encoding="utf-8")
    return path


def test_parses_export(export):
    assert provider.read_transactions(export) == [
        Transaction(date(2024, 2, 3), "Amazon eu sarl", Decimal("-12.50"), memo="Max Mustermann"),
        Transaction(date(2024, 2, 4), "Zahlung erhalten", Decimal("500.00"), memo="Max Mustermann"),
        Transaction(date(2024, 2, 5), "Shell tankstelle", Decimal("-1234.56"), memo="Erika Mustermann"),
    ]


def test_charges_are_outflow_and_payments_are_inflow(export):
    """Legacy wrote charges as negative inflow and payments as negative outflow."""
    charge, payment, _ = provider.read_transactions(export)

    assert (charge.outflow, charge.inflow) == (Decimal("12.50"), 0)
    assert (payment.outflow, payment.inflow) == (0, Decimal("500.00"))


def test_matches_legacy_parser(export):
    """Legacy got the signed net amount right; only its column split was wrong."""
    assert provider.read_transactions(export) == legacy_transactions("americanexpress", export)
