"""StarMoney. Semicolon CSV with a header row and 20 columns."""

from ..parsing import parse_amount, parse_date
from ..transaction import Transaction
from .base import Provider, Row
from .sources import csv_source

COLUMNS = 20


def parse_row(row: Row) -> Transaction:
    if len(row) != COLUMNS:
        raise ValueError(f"Expected {COLUMNS} columns, got {len(row)}")
    date, _text_key, payee, memo, *_split_and_tax_columns, amount, _balance = row
    number, _currency = amount.rsplit(" ", 1)
    return Transaction(
        date=parse_date(date, "%d.%m.%Y"),
        payee=payee.title(),
        amount=parse_amount(number, decimal_mark=",", thousands_mark="."),
        memo=memo.capitalize(),
    )


provider = Provider(
    key="starmoney",
    name="StarMoney",
    read_rows=csv_source(delimiter=";", skip_rows=1),
    parse_row=parse_row,
)
