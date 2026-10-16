"""Eika and other SDC portal banks. Semicolon CSV, no header.

Columns: booking date, transaction date, text, amount, balance.
The text field packs payee, card details and dates together; we pick them apart.
"""

import re

from ..parsing import parse_amount, parse_date
from ..transaction import Transaction
from .base import Provider, Row
from .sources import csv_source

# "Varekjøp REMA 1000 betal dato 2024-03-12"
_PURCHASE_PAYEE = re.compile(r"(?<=Varekjøp ).+?(?= betal dato)")
_PURCHASE_DATE = re.compile(r"\d{4}-\d{2}-\d{2}$")

# "VISA VARE <16 chars> 12.03  EUR 12,50 CAFE PARIS Kurs 11,50", tried in order.
_VISA_PREFIX = r"(?<=VISA VARE \w{16} )(?P<date>\d{2}.\d{2})  ?"
_VISA_COST = r"(?P<cost>\w{0,3} ?\d*?,?\d*?) "
_VISA_PATTERNS = [
    re.compile(_VISA_PREFIX + _VISA_COST + r"(?P<payee>.+?) (?=Kurs)"),
    re.compile(_VISA_PREFIX + _VISA_COST + r"(?P<payee>.+)"),
    re.compile(_VISA_PREFIX + r"(?P<payee>.+)"),
]

# "Lønn - ACME AS"
_SALARY_PAYER = re.compile(r"(?<=Lønn - ).*")


def parse_row(row: Row) -> Transaction:
    booking_date, _transaction_date, text, amount, _balance = row
    payee, memo, date = text, "", parse_date(booking_date, "%d.%m.%Y")

    if text.startswith("Varekjøp"):
        payee = _required(_PURCHASE_PAYEE.search(text), text)[0]
        date = parse_date(_required(_PURCHASE_DATE.search(text), text)[0], "%Y-%m-%d")
    elif text.startswith("VISA VARE"):
        payee, memo = _visa_purchase(text)
    elif text.startswith("Lønn"):
        payee = _required(_SALARY_PAYER.search(text), text)[0]

    return Transaction(
        date=date,
        payee=payee,
        amount=parse_amount(amount, decimal_mark=",", thousands_mark="."),
        memo=memo,
    )


def _visa_purchase(text: str) -> tuple[str, str]:
    """Payee and memo. The memo is the foreign amount, e.g. "EUR 12,50", unless it is zero."""
    match = next(filter(None, (pattern.search(text) for pattern in _VISA_PATTERNS)), None)
    fields = _required(match, text).groupdict()
    cost = fields.get("cost") or ""
    return fields["payee"], "" if cost == "0,00" else cost


def _required(match: re.Match | None, text: str) -> re.Match:
    if match is None:
        raise ValueError(f"Unrecognised transaction text: {text!r}")
    return match


provider = Provider(
    key="eika",
    name="Eika (SDC portal banks)",
    read_rows=csv_source(encoding="utf-8-sig", delimiter=";"),
    parse_row=parse_row,
)
