"""HypoVereinsbank. UTF-16-LE semicolon CSV with a header row."""

from ..parsing import parse_amount, parse_date
from ..transaction import Transaction
from .base import Provider, Row
from .sources import csv_source


def parse_row(row: Row) -> Transaction:
    _account_no, booking_date, _transaction_date, payee1, payee2, text, amount, _currency = row
    # Without a payee, the booking text names the counterparty. The leading space in a
    # payee2-only memo is legacy output, kept so old converted rows still dedup.
    payee, memo = (payee1, text.capitalize()) if payee1 else (text, "")
    if payee2:
        memo += " Empfänger 2: " + payee2.capitalize()
    return Transaction(
        date=parse_date(booking_date, "%d.%m.%Y"),
        payee=payee.capitalize(),
        amount=parse_amount(amount, decimal_mark=",", thousands_mark="."),
        memo=memo,
    )


provider = Provider(
    key="hypovereinsbank",
    name="HypoVereinsbank",
    read_rows=csv_source(encoding="utf-16-le", delimiter=";", skip_rows=1),
    parse_row=parse_row,
)
