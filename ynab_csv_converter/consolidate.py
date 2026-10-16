"""Merge all converted files of a formula into one."""

import os
from dataclasses import dataclass
from pathlib import Path

from . import store, ynab_csv
from .coverage import DateRange, span_of
from .formula import Formula
from .transaction import Transaction


@dataclass(frozen=True)
class Consolidation:
    originals: list[store.StoredFile]
    transactions: list[Transaction]

    @property
    def span(self) -> DateRange | None:
        return span_of(self.transactions)


def plan_consolidation(formula: Formula) -> Consolidation:
    """Read every converted file. Rows are kept as is: identical rows are real transactions."""
    originals = store.converted_files(formula.outpath, formula.outprefix)
    transactions = [row for stored in originals for row in store.read_converted(stored.path)]
    return Consolidation(originals, transactions)


def consolidate(formula: Formula, consolidation: Consolidation) -> Path | None:
    """Write the merged file, then delete the originals. Returns the merged file, if any rows.

    The merged file replaces its target in one step, so a crash leaves either the originals
    or the merged file plus leftover originals. Never fewer rows.
    """
    originals = {stored.path for stored in consolidation.originals}
    merged = None
    if consolidation.span is not None:
        merged = _target(formula, consolidation.span, originals)
        rows = sorted(consolidation.transactions, key=lambda transaction: transaction.date)
        _write_atomically(merged, rows)
    for path in originals - {merged}:
        path.unlink()
    return merged


def _target(formula: Formula, span: DateRange, originals: set[Path]) -> Path:
    """The plain name for `span`. Overwriting an original is fine, its rows are in the merge."""
    path = store.canonical_path(formula.outpath, formula.outprefix, span, store.CONVERTED_SUFFIX)
    if path in originals or not path.exists():
        return path
    return store.free_path(formula.outpath, formula.outprefix, span, store.CONVERTED_SUFFIX)


def _write_atomically(path: Path, transactions: list[Transaction]) -> None:
    # The leading dot keeps the temp file out of the store's name pattern.
    temp = path.with_name(f".{path.name}.tmp")
    try:
        ynab_csv.write(temp, transactions)
        os.replace(temp, path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise
