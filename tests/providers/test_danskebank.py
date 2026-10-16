from datetime import date
from decimal import Decimal

import pytest

from ynab_csv_converter.providers.base import ParseError
from ynab_csv_converter.providers.danskebank import provider
from ynab_csv_converter.transaction import Transaction

EXPORT = (
    '"Dato";"Tekst";"Beløb";"Saldo";"Status";"Afstemt"\n'
    '"02.01.2024";"Føtex Aarhus    12345";"-1.234,50";"10.000,00";"Udført";"Ja"\n'
    '"03.01.2024";"VDK USD  1.234,56";"-8.500,00";"1.500,00";"Udført";"Nej"\n'
    '"04.01.2024";"Overførsel";"500,00";"2.000,00";"Udført";"Nej"\n'
)


def write_export(tmp_path, content=EXPORT):
    path = tmp_path / "export.csv"
    path.write_text(content, encoding="iso-8859-1")
    return path


def test_parses_export(tmp_path):
    assert provider.read_transactions(write_export(tmp_path)) == [
        Transaction(date(2024, 1, 2), "Føtex Aarhus", Decimal("-1234.50"), memo="txn #12345"),
        Transaction(date(2024, 1, 3), "VisaDankort USD", Decimal("-8500.00"), memo="USD 1.234,56"),
        Transaction(date(2024, 1, 4), "Overførsel", Decimal("500.00")),
    ]


def test_rejects_pending_rows(tmp_path):
    pending = EXPORT.splitlines()[0] + '\n"05.01.2024";"Netto";"-10,00";"1.990,00";"Venter";"Nej"\n'
    with pytest.raises(ParseError, match="not completed"):
        provider.read_transactions(write_export(tmp_path, pending))
