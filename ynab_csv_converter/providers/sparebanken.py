"""Sparebanken. Semicolon CSV with a header row.

Money in is a positive "Inn" column, money out a negative "Ut" column.
"""

from decimal import Decimal

from ..parsing import parse_amount, parse_date
from ..transaction import Transaction
from .base import Provider, Row
from .sources import csv_source


def parse_row(row: Row) -> Transaction:
    inflow = _amount(row.get("Inn"))
    outflow = _amount(row.get("Ut"))
    if inflow < 0 or outflow > 0:
        raise ValueError(f"Expected positive Inn and negative Ut, got Inn={inflow} Ut={outflow}")
    if not inflow and not outflow:
        raise ValueError("Neither Inn nor Ut has an amount")
    return Transaction(
        date=parse_date(row["Dato"], "%d.%m.%Y"),
        payee=row["Beskrivelse"],
        amount=inflow + outflow,
    )


def _amount(text: str | None) -> Decimal:
    return parse_amount(text, decimal_mark=",") if text else Decimal(0)


provider = Provider(
    key="sparebanken",
    name="Sparebanken",
    read_rows=csv_source(encoding="utf-8-sig", delimiter=";", keyed_by_header=True),
    parse_row=parse_row,
)
