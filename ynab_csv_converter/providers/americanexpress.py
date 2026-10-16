"""American Express. Comma CSV with a header row."""

import re

from ..parsing import parse_amount, parse_date
from ..transaction import Transaction
from .base import Provider, Row
from .sources import csv_source

# Amex pads the merchant name with two or more spaces before location details.
_PAYEE_PADDING = re.compile(r"  .*$")


def parse_row(row: Row) -> Transaction:
    date, payee, card_member, _account_no, amount = row
    return Transaction(
        date=parse_date(date, "%d/%m/%Y"),
        payee=_PAYEE_PADDING.sub("", payee.capitalize()),
        # Amex lists charges as positive amounts. They are money leaving the account.
        amount=-parse_amount(amount, decimal_mark=","),
        memo=card_member.title(),
    )


provider = Provider(
    key="americanexpress",
    name="American Express",
    read_rows=csv_source(skip_rows=1),
    parse_row=parse_row,
)
