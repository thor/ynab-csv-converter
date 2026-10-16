"""Locale-free helpers for turning bank export text into typed values."""

import re
from datetime import date, datetime
from decimal import Decimal

_PLAIN_NUMBER = re.compile(r"^[-+]?\d+(\.\d+)?$")


def parse_amount(text: str, *, decimal_mark: str, thousands_mark: str = "") -> Decimal:
    """Parse "1.234,56" style amounts without touching the process locale.

    >>> parse_amount("-1.234,56", decimal_mark=",", thousands_mark=".")
    Decimal('-1234.56')
    """
    normalized = text.strip().replace("−", "-")
    if thousands_mark:
        normalized = normalized.replace(thousands_mark, "")
    normalized = normalized.replace(decimal_mark, ".")
    if not _PLAIN_NUMBER.match(normalized):
        raise ValueError(f"Not an amount: {text!r}")
    return Decimal(normalized)


def parse_date(text: str, format: str) -> date:
    return datetime.strptime(text.strip(), format).date()
