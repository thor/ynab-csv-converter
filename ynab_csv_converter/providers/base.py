"""What a provider is, and how the framework runs one."""

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..transaction import Transaction

Row = Sequence[Any]
"""One record from a source file. Cells are str for CSV, native values (datetime, float) for xlsx."""

NumberedRow = tuple[int, Row]
"""A row and its 1-based line number in the source file, for error messages."""

RowReader = Callable[[Path], Iterable[NumberedRow]]
RowParser = Callable[[Row], Transaction | None]


@dataclass(frozen=True)
class Provider:
    """A bank or export format.

    `read_rows` knows the file format (see `sources`). `parse_row` knows the bank's
    conventions and returns None for rows that are not transactions.
    """

    key: str
    name: str
    read_rows: RowReader
    parse_row: RowParser

    def read_transactions(self, path: Path) -> list[Transaction]:
        transactions = []
        for line_number, row in self.read_rows(path):
            try:
                transaction = self.parse_row(row)
            except Exception as error:
                raise ParseError(path, line_number, row) from error
            if transaction is not None:
                transactions.append(transaction)
        return transactions


class ParseError(Exception):
    def __init__(self, path: Path, line_number: int, row: Row):
        self.path = path
        self.line_number = line_number
        self.row = row
        super().__init__(f"{path}:{line_number}: could not parse row {list(row)!r}")
