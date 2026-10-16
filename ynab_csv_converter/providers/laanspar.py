"""Lån & Spar Bank. Semicolon CSV with a header row."""

from ..parsing import parse_amount, parse_date
from ..transaction import Transaction
from .base import Provider, Row
from .sources import csv_source


def parse_row(row: Row) -> Transaction:
    booking_date, text, amount, _balance = row
    return Transaction(
        date=parse_date(booking_date, "%d-%m-%Y"),
        payee=text,
        amount=parse_amount(amount, decimal_mark=",", thousands_mark="."),
    )


provider = Provider(
    key="laanspar",
    name="Lån & Spar Bank",
    read_rows=csv_source(encoding="utf-8-sig", delimiter=";", skip_rows=1),
    parse_row=parse_row,
)
