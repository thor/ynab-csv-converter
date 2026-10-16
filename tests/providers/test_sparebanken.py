from datetime import date
from decimal import Decimal

import pytest

from ynab_csv_converter.providers.base import ParseError
from ynab_csv_converter.providers.sparebanken import provider
from ynab_csv_converter.transaction import Transaction

HEADER = '"Dato";"Beskrivelse";"Rentedato";"Inn";"Ut";"Til konto";"Fra konto"\n'
EXPORT = HEADER + (
    '"01.02.2024";"Lønn ACME";"01.02.2024";"25000,50";"";"12345678901";""\n'
    '"03.02.2024";"Rema 1000";"02.02.2024";"";"-1234,5";"";"12345678901"\n'
    '"04.02.2024";"Korrigering";"04.02.2024";"100,00";"-30,00";"";""\n'
)


def write_export(tmp_path, content=EXPORT):
    path = tmp_path / "sparebanken.csv"
    path.write_text(content, encoding="utf-8-sig")
    return path


def test_parses_export(tmp_path):
    assert provider.read_transactions(write_export(tmp_path)) == [
        Transaction(date(2024, 2, 1), "Lønn ACME", Decimal("25000.50")),
        Transaction(date(2024, 2, 3), "Rema 1000", Decimal("-1234.5")),
        Transaction(date(2024, 2, 4), "Korrigering", Decimal("70.00")),
    ]


@pytest.mark.parametrize(
    "inflow, outflow",
    [
        pytest.param("", "30,00", id="positive Ut"),
        pytest.param("-30,00", "", id="negative Inn"),
        pytest.param("", "", id="no amount"),
    ],
)
def test_rejects_bad_amounts(tmp_path, inflow, outflow):
    path = write_export(tmp_path, HEADER + f'"04.02.2024";"X";"04.02.2024";"{inflow}";"{outflow}";"";""\n')
    with pytest.raises(ParseError):
        provider.read_transactions(path)
