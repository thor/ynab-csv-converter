"""What a provider is, and how the framework runs one."""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..transaction import Transaction

Row = Sequence[Any] | Mapping[str, Any]
"""One record from a source file.

A sequence of cells, or a header-to-cell mapping when the source is `keyed_by_header`.
Cells are str for CSV and native values (datetime, float, None) for xlsx.
"""

NumberedRow = tuple[int, Row]
"""A row and its 1-based line number in the source file, for error messages."""

RowReader = Callable[[Path], Iterable[NumberedRow]]
RowParser = Callable[[Row], Transaction | None]
CsvConverter = Callable[[Path, Path], None]
"""Writes the workbook at the first path as CSV to the second path."""


@dataclass(frozen=True)
class Provider:
    """A bank or export format.

    `read_rows` knows the file format (see `sources`). `parse_row` knows the bank's
    conventions and returns None for rows that are not transactions.

    `csv_from_xlsx` is for banks that switched from CSV to xlsx exports: the workbook is
    saved as the old CSV first, then parsed and archived like the CSVs before it.
    """

    key: str
    name: str
    read_rows: RowReader
    parse_row: RowParser
    csv_from_xlsx: CsvConverter | None = None

    def read_transactions(self, path: Path) -> list[Transaction]:
        transactions = []
        for line_number, row in self.read_rows(path):
            try:
                transaction = self.parse_row(row)
            except Exception as error:
                raise ParseError(path, line_number, row, error) from error
            if transaction is not None:
                transactions.append(transaction)
        return transactions


class ParseError(Exception):
    def __init__(self, path: Path, line_number: int, row: Row, cause: Exception):
        self.path = path
        self.line_number = line_number
        self.row = row
        cells = dict(row) if isinstance(row, Mapping) else list(row)
        super().__init__(f"{path}:{line_number}: {cause}\n  row: {cells!r}")
