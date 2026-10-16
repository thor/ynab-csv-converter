"""OBOS Bank. Two export flavours share one way of reading the free-text field.

Exports are tab separated ISO-8859-1 with a header row. Each row has a transaction type
(e.g. "Varekjøp", "NETTGIRO") and a text such as "Nettgiro til: Ola Betalt: 01.03.24".
Every type maps to a `Kind` that decides how the text becomes payee, memo and date.
"""

import re
from datetime import date
from enum import Enum, auto

from ...parsing import parse_amount, parse_date
from ...transaction import Transaction
from ..sources import csv_source

read_rows = csv_source(encoding="iso8859-1", delimiter="\t", skip_rows=1)


class Kind(Enum):
    INCOMING = auto()
    """Money in gets the "To be budgeted" category."""
    VIPPS = auto()
    PURCHASE = auto()
    """Card purchase. The text holds the real purchase date, payee and any foreign amount."""
    OTHER = auto()


AVTALEGIRO_TYPES = ("AvtaleGiro", "AVTGI", "IAVTG")
STOCK_TYPES = ("VPAPIR",)

# "*1234  28.12 EUR 12.50 CAFE PARIS Kurs: 11.52"
_CARD = r"(?P<card>^\*\d{4} )"
_SHORT_DATE = r"(?P<date>\d{2}\.\d{2})"
# Unlike _PURCHASE, this needs a space before the date. Kept apart so dates stay as legacy.
_PURCHASE_DATE = re.compile(rf"{_CARD}? {_SHORT_DATE}")
_PURCHASE = re.compile(
    rf"({_CARD} )?{_SHORT_DATE} ((?P<currency>\w{{3}}) (?P<amount>\d{{1,}}\.\d{{1,2}}) )?"
    r"(?P<payee>.*?)( Kurs: (?P<rate>\d*\.\d*)|$)"
)
# "Til: Ola Nordmann Betalt: 01.03.24"
_META = re.compile(
    r"(?P<key>Nettgiro til|Nettgiro fra|Fra|Til|Betalt): (?P<value>.*?)(?= (Fra|Til|Betalt)|$)"
)
_PAYEE_KEYS = ("Til", "Fra", "Nettgiro fra", "Nettgiro til")


def to_transaction(
    *, booking_date: str, type: str, text: str, amount: str, kinds: dict[str, Kind], account: str = ""
) -> Transaction:
    if type not in kinds:
        raise ValueError(f"Unknown transaction type {type!r}")
    kind = kinds[type]
    booked = parse_date(booking_date, "%d.%m.%Y")
    signed_amount = parse_amount(amount, decimal_mark=",")

    if kind is Kind.PURCHASE:
        txn_date = purchase_date(booked, text)
        payee, memo = describe_purchase(text)
    else:
        txn_date = booked
        payee, memo = describe_transfer(type, text, vipps=kind is Kind.VIPPS)

    if account:
        memo += f" ({account})"

    return Transaction(
        date=txn_date,
        payee=payee,
        amount=signed_amount,
        memo=memo,
        category="To be budgeted" if kind is Kind.INCOMING and signed_amount > 0 else "",
    )


def purchase_date(booked: date, text: str) -> date:
    """The "dd.mm" purchase date in the text, in the booking year or the one before.

    A purchase on 28.12 booked on 02.01 belongs to the previous year.
    """
    match = _PURCHASE_DATE.search(text)
    if not match:
        return booked
    day, month = map(int, match["date"].split("."))
    purchased = date(booked.year, month, day)
    return purchased if purchased <= booked else purchased.replace(year=booked.year - 1)


def describe_purchase(text: str) -> tuple[str, str]:
    """Payee, and a memo with the foreign amount for card purchases abroad."""
    match = _PURCHASE.search(text)
    if not match:
        raise ValueError(f"Unrecognised purchase text: {text!r}")
    memo = ""
    if match["card"] and match["currency"] and match["currency"] != "NOK":
        # Rate is None without "Kurs:", giving "ved None". Kept as legacy wrote it.
        memo = f"Valuta: {match['amount']} {match['currency']} ved {match['rate']}"
    return match["payee"], memo


def describe_transfer(type: str, text: str, *, vipps: bool) -> tuple[str, str]:
    """Payee and memo from "Key: value" pairs in the text.

    The first Til/Fra counterparty becomes the payee, everything else goes to the memo.
    """
    payee = "Vipps" if vipps else ""
    memo = "" if vipps else type.lower().capitalize()
    if type in AVTALEGIRO_TYPES:
        memo = "AvtaleGiro"
    elif type in STOCK_TYPES:
        memo = "Verdipapir(er)"

    pairs = [(match["key"], match["value"]) for match in _META.finditer(text)]
    if not pairs and type in AVTALEGIRO_TYPES + STOCK_TYPES:
        return text, memo

    for key, value in pairs:
        if key in _PAYEE_KEYS and not payee:
            payee = value
        else:
            memo += f" {key}: {value}"
    return payee, memo
