"""Row readers for the file formats banks export.

Each factory returns a `RowReader`. Blank rows are skipped everywhere.
"""

import csv
import zipfile
from collections.abc import Iterator, Mapping
from datetime import date
from pathlib import Path

from .base import CsvConverter, NumberedRow, RowReader


def csv_source(
    *,
    encoding: str = "utf-8",
    delimiter: str = ",",
    quotechar: str = '"',
    skip_rows: int = 0,
    keyed_by_header: bool = False,
) -> RowReader:
    """Read a CSV file.

    `skip_rows` drops leading lines. With `keyed_by_header`, the next line is the header
    and rows are dicts keyed by it.
    """

    def read(path: Path) -> Iterator[NumberedRow]:
        with open(path, encoding=encoding, newline="") as handle:
            reader = csv.reader(handle, delimiter=delimiter, quotechar=quotechar)
            yield from _numbered(((reader.line_num, row) for row in reader), skip_rows, keyed_by_header)

    return read


def xlsx_source(*, sheet: str | None = None, skip_rows: int = 0, keyed_by_header: bool = False) -> RowReader:
    """Read an Excel workbook. Uses the active sheet unless `sheet` is given.

    `skip_rows` and `keyed_by_header` work as for `csv_source`.
    """

    def read(path: Path) -> Iterator[NumberedRow]:
        from openpyxl import load_workbook
        from openpyxl.utils.exceptions import InvalidFileException

        try:
            workbook = load_workbook(path, read_only=True, data_only=True)
        except (zipfile.BadZipFile, InvalidFileException) as error:
            raise ValueError(f"{path}: not an Excel workbook ({error})") from error
        try:
            worksheet = workbook[sheet] if sheet else workbook.active
            rows = enumerate(worksheet.iter_rows(values_only=True), start=1)
            yield from _numbered(rows, skip_rows, keyed_by_header)
        finally:
            workbook.close()

    return read


def by_suffix(readers: Mapping[str, RowReader]) -> RowReader:
    """Pick a reader from the file suffix, e.g. {".csv": csv_source(), ".xlsx": xlsx_source()}."""

    def read(path: Path) -> Iterator[NumberedRow]:
        suffix = path.suffix.lower()
        if suffix not in readers:
            supported = ", ".join(sorted(readers))
            raise ValueError(f"{path}: unsupported file type {suffix!r}, expected one of {supported}")
        yield from readers[suffix](path)

    return read


def xlsx_to_csv(
    *, date_format: str, delimiter: str = ",", encoding: str = "utf-8-sig", sheet: str | None = None
) -> CsvConverter:
    """Save a workbook as CSV the way banks export it: dates in `date_format`, numbers without
    trailing zeros (-40, 13.97075), empty cells as empty strings."""

    def convert(xlsx_path: Path, csv_path: Path) -> None:
        with open(csv_path, "w", encoding=encoding, newline="") as handle:
            writer = csv.writer(handle, delimiter=delimiter)
            for _, row in xlsx_source(sheet=sheet)(xlsx_path):
                writer.writerow([_as_csv_text(cell, date_format) for cell in row])

    return convert


def _as_csv_text(cell, date_format: str) -> str:
    if cell is None:
        return ""
    if isinstance(cell, date):
        return cell.strftime(date_format)
    if isinstance(cell, float) and cell.is_integer():
        return str(int(cell))
    return str(cell)


def _numbered(rows: Iterator[NumberedRow], skip_rows: int, keyed_by_header: bool) -> Iterator[NumberedRow]:
    header = None
    for line_number, row in rows:
        if line_number <= skip_rows or _is_blank(row):
            continue
        if keyed_by_header and header is None:
            header = [str(cell).strip() for cell in row]
            continue
        yield line_number, dict(zip(header, row, strict=False)) if header else row


def _is_blank(row) -> bool:
    return all(cell is None or str(cell).strip() == "" for cell in row)
