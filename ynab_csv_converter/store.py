"""Converted and archived files, named by the date range they hold.

Name: `<prefix>-<last yyyymmdd>-<first yyyymmdd>[-<n>]<suffix>`, newest date first.
Converted files are YNAB CSV (.csv). Archived exports keep the suffix of the source.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from . import ynab_csv
from .coverage import DateRange
from .transaction import Transaction

FILE_DATE_FORMAT = "%Y%m%d"
CONVERTED_SUFFIX = ".csv"


class StoreError(Exception):
    pass


@dataclass(frozen=True)
class StoredFile:
    path: Path
    span: DateRange


def list_files(folder: Path, prefix: str, suffix: str | None = None) -> list[StoredFile]:
    """Files in `folder` named after `prefix` and a date range, oldest first.

    Other files are ignored. `suffix` limits the result to one file type.
    """
    if not folder.is_dir():
        return []
    pattern = re.compile(re.escape(prefix) + r"-(?P<last>\d{8})-(?P<first>\d{8})(?:-\d+)?(?P<suffix>\.\w+)?")
    found = []
    for path in folder.iterdir():
        match = pattern.fullmatch(path.name)
        if not match or not path.is_file():
            continue
        if suffix is not None and (match["suffix"] or "").lower() != suffix:
            continue
        span = _span(match["first"], match["last"])
        if span is not None:
            found.append(StoredFile(path, span))
    return sorted(found, key=lambda stored: (stored.span, stored.path.name))


def free_path(folder: Path, prefix: str, span: DateRange, suffix: str) -> Path:
    """First unused name for `span`, adding -1, -2, ... when taken."""
    stem = f"{prefix}-{span.last:{FILE_DATE_FORMAT}}-{span.first:{FILE_DATE_FORMAT}}"
    path = folder / f"{stem}{suffix}"
    increment = 0
    while path.exists():
        increment += 1
        path = folder / f"{stem}-{increment}{suffix}"
    return path


def converted_files(folder: Path, prefix: str) -> list[StoredFile]:
    return list_files(folder, prefix, CONVERTED_SUFFIX)


def read_converted(path: Path) -> list[Transaction]:
    try:
        return ynab_csv.read(path)
    except (ValueError, ArithmeticError) as error:
        raise StoreError(f"{path}: not a valid YNAB CSV file: {error}") from error


def _span(first: str, last: str) -> DateRange | None:
    try:
        return DateRange(_parse(first), _parse(last))
    except ValueError:
        return None


def _parse(text: str) -> date:
    return datetime.strptime(text, FILE_DATE_FORMAT).date()
