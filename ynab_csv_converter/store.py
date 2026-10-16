"""Converted and archived files, named by the date range they hold.

Name: `<prefix>-<last yyyymmdd>-<first yyyymmdd>[-<n>]<suffix>`, newest date first.
Converted files are YNAB CSV (.csv). Archived exports keep the suffix of the source.
"""

import csv
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
    Raises StoreError for near misses like `<prefix>-20260731-20260701 copy.csv`:
    skipping them would silently drop their dates and rows.
    """
    if not folder.is_dir():
        return []
    stem = re.escape(prefix) + r"-(?P<last>\d{8})-(?P<first>\d{8})"
    pattern = re.compile(stem + r"(?:-\d+)?(?P<suffix>\.\w+)?")
    lookalike = re.compile(stem)
    found = []
    for path in folder.iterdir():
        if not path.is_file() or not lookalike.match(path.name):
            continue
        match = pattern.fullmatch(path.name)
        if not match:
            raise StoreError(
                f"{path}: looks like a stored file but the name does not match "
                f"{prefix}-<yyyymmdd>-<yyyymmdd>[-n].<suffix>. Rename or remove it."
            )
        if suffix is not None and (match["suffix"] or "").lower() != suffix:
            continue
        span = _span(match["first"], match["last"])
        if span is not None:
            found.append(StoredFile(path, span))
    return sorted(found, key=lambda stored: (stored.span, stored.path.name))


def free_path(folder: Path, prefix: str, span: DateRange, suffix: str) -> Path:
    """First unused name for `span`, adding -1, -2, ... when taken."""
    path = canonical_path(folder, prefix, span, suffix)
    increment = 0
    while path.exists():
        increment += 1
        path = folder / f"{_stem(prefix, span)}-{increment}{suffix}"
    return path


def canonical_path(folder: Path, prefix: str, span: DateRange, suffix: str) -> Path:
    return folder / f"{_stem(prefix, span)}{suffix}"


def converted_files(folder: Path, prefix: str) -> list[StoredFile]:
    return list_files(folder, prefix, CONVERTED_SUFFIX)


def read_converted(path: Path) -> list[Transaction]:
    try:
        return ynab_csv.read(path)
    except (ValueError, ArithmeticError, csv.Error) as error:
        raise StoreError(f"{path}: not a valid YNAB CSV file: {error}") from error


def _stem(prefix: str, span: DateRange) -> str:
    return f"{prefix}-{span.last:{FILE_DATE_FORMAT}}-{span.first:{FILE_DATE_FORMAT}}"


def _span(first: str, last: str) -> DateRange | None:
    try:
        return DateRange(_parse(first), _parse(last))
    except ValueError:
        return None


def _parse(text: str) -> date:
    return datetime.strptime(text, FILE_DATE_FORMAT).date()
