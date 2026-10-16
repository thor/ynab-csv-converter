"""Run the legacy formats/ parsers so ported providers can be checked against them.

Delete together with ynab_csv_converter/formats/.
"""

import importlib
import locale
from decimal import Decimal

import pytest

from ynab_csv_converter.transaction import Transaction


def legacy_transactions(format_key: str, path) -> list[Transaction]:
    """Legacy parsers call locale.setlocale; restore it so tests stay independent."""
    saved_locale = locale.setlocale(locale.LC_ALL)
    try:
        return _convert(format_key, path)
    except locale.Error as error:
        pytest.skip(f"legacy {format_key} needs a locale this machine lacks: {error}")
    finally:
        locale.setlocale(locale.LC_ALL, saved_locale)


def _convert(format_key: str, path) -> list[Transaction]:
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
