"""Danske Bank. Latin-1 semicolon CSV with a header row."""

import re

from ..parsing import parse_amount, parse_date
from ..transaction import Transaction
from .base import Provider, Row
from .sources import csv_source

TEXT_WITH_TRANSACTION_NUMBER = re.compile(r"^(?P<payee>.+\S)\s+(?P<number>\d{5})$")
VISA_DANKORT_FOREIGN = re.compile(r"^VDK (?P<currency>[A-Z]{3})\s+(?P<amount>\d{1,3}(\.\d{3})*,\d{2})$")


def parse_row(row: Row) -> Transaction:
    booking_date, text, amount, _balance, status, _cleared = row
    if status != "Udført":
        # Pending rows change before they settle. Importing them would create duplicates later.
        raise ValueError(f"Transaction not completed (status {status!r})")
    payee, memo = parse_text(text)
    return Transaction(
        date=parse_date(booking_date, "%d.%m.%Y"),
        payee=payee,
        memo=memo,
        amount=parse_amount(amount, decimal_mark=",", thousands_mark="."),
    )


def parse_text(text: str) -> tuple[str, str]:
    """Split the bank text into payee and memo."""
    if match := TEXT_WITH_TRANSACTION_NUMBER.match(text):
        return match["payee"], f"txn #{match['number']}"
    if match := VISA_DANKORT_FOREIGN.match(text):
        return f"VisaDankort {match['currency']}", f"{match['currency']} {match['amount']}"
    return text, ""


provider = Provider(
    key="danskebank",
    name="Danske Bank",
    read_rows=csv_source(encoding="iso-8859-1", delimiter=";", skip_rows=1),
    parse_row=parse_row,
)
