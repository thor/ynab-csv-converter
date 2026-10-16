from datetime import date
from decimal import Decimal

import pytest

from ynab_csv_converter.providers.base import ParseError
from ynab_csv_converter.providers.eika import provider
from ynab_csv_converter.transaction import Transaction

CARD = "1234567890123456"
EXPORT = (
    '"14.03.2024";"14.03.2024";"Varekjøp REMA 1000 OSLO betal dato 2024-03-12";"-1.234,50";"10.000,00"\n'
    f'"15.03.2024";"15.03.2024";"VISA VARE {CARD} 12.03  EUR 12,50 CAFE Kurs 11,50";"-143,75";"9.856,25"\n'
    f'"15.03.2024";"15.03.2024";"VISA VARE {CARD} 13.03  0,00 REMA 1000";"-99,00";"9.757,25"\n'
    f'"15.03.2024";"15.03.2024";"VISA VARE {CARD} 13.03  NOK 99,00 KIWI 123 OSLO";"-99,00";"9.658,25"\n'
    f'"16.03.2024";"16.03.2024";"VISA VARE {CARD} 14.03 KIWI 123";"-45,00";"9.613,25"\n'
    '"20.03.2024";"20.03.2024";"Lønn - ACME AS";"35.000,00";"44.613,25"\n'
    '"21.03.2024";"21.03.2024";"Overføring til sparekonto";"-500,00";"44.113,25"\n'
)


def write_export(tmp_path, content=EXPORT):
    path = tmp_path / "eika.csv"
    path.write_text(content, encoding="utf-8-sig")
    return path


def test_parses_export(tmp_path):
    assert provider.read_transactions(write_export(tmp_path)) == [
        Transaction(date(2024, 3, 12), "REMA 1000 OSLO", Decimal("-1234.50")),
        Transaction(date(2024, 3, 15), "CAFE", Decimal("-143.75"), memo="EUR 12,50"),
        Transaction(date(2024, 3, 15), "REMA 1000", Decimal("-99.00")),
        Transaction(date(2024, 3, 15), "KIWI 123 OSLO", Decimal("-99.00"), memo="NOK 99,00"),
        Transaction(date(2024, 3, 16), "KIWI 123", Decimal("-45.00")),
        Transaction(date(2024, 3, 20), "ACME AS", Decimal("35000.00")),
        Transaction(date(2024, 3, 21), "Overføring til sparekonto", Decimal("-500.00")),
    ]


def test_rejects_unrecognised_salary_text(tmp_path):
    path = write_export(tmp_path, '"20.03.2024";"20.03.2024";"Lønn ACME";"1,00";"1,00"\n')
    with pytest.raises(ParseError, match="Unrecognised"):
        provider.read_transactions(path)
