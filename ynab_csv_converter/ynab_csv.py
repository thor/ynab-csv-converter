"""Read and write the YNAB CSV import format."""

import csv
from collections.abc import Iterable
from decimal import Decimal
from pathlib import Path

from .parsing import parse_date
from .transaction import Transaction

HEADER = ["Date", "Payee", "Category", "Memo", "Outflow", "Inflow"]
DATE_FORMAT = "%d/%m/%Y"


def read(path: Path) -> list[Transaction]:
    with open(path, encoding="utf-8", newline="") as handle:
        rows = csv.reader(handle)
        next(rows, None)
        return [_from_row(row) for row in rows if row]


def write(path: Path, transactions: Iterable[Transaction]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        for transaction in transactions:
            writer.writerow([
                transaction.date.strftime(DATE_FORMAT),
                transaction.payee,
                transaction.category,
                transaction.memo,
                f"{transaction.outflow:.2f}",
                f"{transaction.inflow:.2f}",
            ])


def _from_row(row: list[str]) -> Transaction:
    date, payee, category, memo, outflow, inflow = row
    return Transaction(
        date=parse_date(date, DATE_FORMAT),
        payee=payee,
        amount=Decimal(inflow) - Decimal(outflow),
        memo=memo,
        category=category,
    )
