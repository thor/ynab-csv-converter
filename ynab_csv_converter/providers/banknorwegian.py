"""Bank Norwegian credit card. Comma CSV with a header row, dot decimals.

Newer exports are xlsx with the same columns; they are saved as that CSV before import.

Columns: date, payee, type, currency amount, currency rate, currency, amount (NOK),
merchant area, merchant category, booking date, value date.
"""

from ..parsing import parse_amount, parse_date
from ..transaction import Transaction
from .base import Provider, Row
from .sources import csv_source, xlsx_to_csv


def parse_row(row: Row) -> Transaction:
    (
        txn_date,
        payee,
        _type,
        currency_amount,
        _currency_rate,
        currency,
        amount_text,
        _merchant_area,
        merchant_category,
        _booking_date,
        _value_date,
    ) = row
    amount = parse_amount(amount_text, decimal_mark=".")

    memo = "" if amount > 0 else merchant_category
    if currency != "NOK":
        # Leading space when the memo is empty: kept, converted CSVs are the dedup baseline.
        memo += f" {currency_amount} {currency}"

    return Transaction(date=parse_date(txn_date, "%Y/%m/%d"), payee=payee, amount=amount, memo=memo)


provider = Provider(
    key="banknorwegian",
    name="Bank Norwegian",
    read_rows=csv_source(encoding="utf-8-sig", skip_rows=1),
    parse_row=parse_row,
    csv_from_xlsx=xlsx_to_csv(date_format="%Y/%m/%d"),
)
