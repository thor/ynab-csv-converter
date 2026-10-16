"""Run the legacy formats/ parsers so ported providers can be checked against them.

Delete together with ynab_csv_converter/formats/.
"""

import importlib
from decimal import Decimal

from ynab_csv_converter.transaction import Transaction


def legacy_transactions(format_key: str, path) -> list[Transaction]:
    module = importlib.import_module(f"ynab_csv_converter.formats.{format_key}")
    return [
        Transaction(
            date=line.date.date(),
            payee=line.payee,
            amount=(Decimal(str(line.inflow)) - Decimal(str(line.outflow))).quantize(Decimal("0.01")),
            memo=line.memo,
            category=line.category,
        )
        for line in module.getlines(str(path))
    ]
