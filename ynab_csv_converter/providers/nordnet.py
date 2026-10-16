"""Nordnet. UTF-16 tab-separated export with a header row. Converts amounts to DKK."""

from decimal import Decimal

from ..parsing import parse_amount, parse_date
from ..transaction import Transaction, scale_amount
from .base import Provider, Row
from .sources import csv_source

DKK_PER_UNIT = {"EUR": Decimal("7.46"), "USD": Decimal("6.68"), "DKK": Decimal(1), "NOK": Decimal(1)}
"""Fixed rates inherited from the original converter. NOK at 1 is as legacy had it."""


def parse_row(row: Row) -> Transaction:
    (
        _id, booking_date, _trade_date, _value_date, _portfolio,
        transaction_type, security, instrument_type, _isin, quantity, price,
        _interest, _fee, _fee_currency, amount, currency,
        _purchase_value, _result, _total_quantity, _balance, exchange_rate, _text,
        _cancel_date, _slip_number, _verification_number, _broker_fee, _broker_fee_currency,
    ) = row  # fmt: skip
    if "aktie" in instrument_type.lower():
        payee = f"{transaction_type.capitalize()} {security}"
        memo = _trade_memo(quantity, price, currency, exchange_rate)
    else:
        payee = transaction_type.capitalize()
        memo = ""
    return Transaction(
        date=parse_date(booking_date, "%Y-%m-%d"),
        payee=payee,
        memo=memo,
        amount=scale_amount(_parse_number(amount), DKK_PER_UNIT[currency]),
    )


def _trade_memo(quantity: str, price: str, currency: str, exchange_rate: str) -> str:
    rate = _parse_number(exchange_rate)
    # float() keeps the legacy text (e.g. "1234.5600000000001"); existing converted files dedup on it.
    local_price = float(_parse_number(price)) * float(rate)
    memo = f"{quantity} stk. til {currency} {local_price}"
    if rate != 0:
        memo += f" (veksl. {exchange_rate})"
    return memo


def _parse_number(text: str) -> Decimal:
    """Thousands are grouped by a space, or a (narrow) no-break space in some exports."""
    spaced = text.replace("\xa0", " ").replace(" ", " ")
    return parse_amount(spaced, decimal_mark=",", thousands_mark=" ")


provider = Provider(
    key="nordnet",
    name="Nordnet",
    read_rows=csv_source(encoding="utf-16", delimiter="\t", skip_rows=1),
    parse_row=parse_row,
)
