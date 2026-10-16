"""OBOS Bank "last transactions" export. Columns: date, type, text, amount."""

from ...transaction import Transaction
from ..base import Provider, Row
from . import Kind, read_rows, to_transaction

KINDS = {
    "Innbetaling": Kind.INCOMING,
    "Overføring": Kind.INCOMING,
    "Vipps overføring": Kind.VIPPS,
    "Varekjøp": Kind.PURCHASE,
    "AvtaleGiro": Kind.OTHER,
    "eFaktura": Kind.OTHER,
    "Betaling": Kind.OTHER,
}


def parse_row(row: Row) -> Transaction:
    booking_date, type, text, amount = row
    return to_transaction(booking_date=booking_date, type=type, text=text, amount=amount, kinds=KINDS)


provider = Provider(
    key="obos.recent", name="OBOS Bank, recent transactions", read_rows=read_rows, parse_row=parse_row
)
