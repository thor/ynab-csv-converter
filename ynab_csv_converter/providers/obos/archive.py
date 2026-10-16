"""OBOS Bank archive export. Columns: date, interest date, type, text, amount, reference, account."""

from ...transaction import Transaction
from ..base import Provider, Row
from . import Kind, read_rows, to_transaction

KINDS = {
    "LØNN": Kind.INCOMING,
    "GIRO": Kind.INCOMING,
    "OVERFØRT": Kind.INCOMING,
    "STRAKSBET": Kind.OTHER,
    "StraksOvf": Kind.VIPPS,
    "VARER": Kind.PURCHASE,
    "VISA VARE": Kind.PURCHASE,
    "AVTGI": Kind.OTHER,
    "IAVTG": Kind.OTHER,
    "E-FAKTURA": Kind.OTHER,
    "NETTGIRO": Kind.OTHER,
    "MOBILGIRO": Kind.OTHER,
    "VPAPIR": Kind.OTHER,
    "KREDITRTE": Kind.OTHER,
}


def parse_row(row: Row) -> Transaction:
    booking_date, _interest_date, type, text, amount, _reference, account = row
    return to_transaction(
        booking_date=booking_date, type=type, text=text, amount=amount, kinds=KINDS, account=account
    )


provider = Provider(key="obos.archive", name="OBOS Bank, archive", read_rows=read_rows, parse_row=parse_row)
