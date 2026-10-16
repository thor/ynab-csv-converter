"""Saxo TraderGO account statement. Excel export, or that export saved as CSV."""

import re
from datetime import date, datetime
from decimal import Decimal

from ..parsing import parse_amount
from ..transaction import Transaction
from .base import Provider, Row
from .sources import by_suffix, csv_source, xlsx_source

MONTHS = {
    name: number for number, name in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)
}
"""English month abbreviations. Spelled out so parsing does not depend on the process locale."""

TEXT_WITH_TRANSACTION_ID = re.compile(r"^(?P<payee>.+) (?P<transaction_id>\d{9,})$")


def parse_row(row: Row) -> Transaction:
    _account_id, _posting_date, value_date, product, net_change, _cash_balance, *_ = row
    payee, memo = parse_text(str(product))
    return Transaction(
        date=parse_value_date(value_date),
        payee=payee,
        memo=memo,
        amount=parse_net_change(net_change),
    )


def parse_value_date(value: str | date) -> date:
    """Excel gives a datetime. CSV text is "15-10-2024" or "15-oct-2024"."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    day, month, year = value.strip().split("-")
    month_number = int(month) if month.isdigit() else MONTHS[month.lower()]
    return date(int(year), month_number, int(day))


def parse_net_change(value: str | float | int) -> Decimal:
    if isinstance(value, int | float):
        return Decimal(str(value))
    return parse_amount(value, decimal_mark=".")


def parse_text(text: str) -> tuple[str, str]:
    if match := TEXT_WITH_TRANSACTION_ID.match(text):
        return match["payee"], f"{match['payee']} txn #{match['transaction_id']}"
    return text, ""


provider = Provider(
    key="saxotradergo",
    name="Saxo TraderGO",
    read_rows=by_suffix(
        {
            ".csv": csv_source(skip_rows=1),
            ".xlsx": xlsx_source(skip_rows=1),
        }
    ),
    parse_row=parse_row,
)
