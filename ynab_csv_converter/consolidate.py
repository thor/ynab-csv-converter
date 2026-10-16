"""Merge all converted files of a formula into one."""

from dataclasses import dataclass
from pathlib import Path

from . import store, ynab_csv
from .coverage import DateRange
from .formula import Formula
from .transaction import Transaction


@dataclass(frozen=True)
class Consolidation:
    originals: list[store.StoredFile]
    transactions: list[Transaction]

    @property
    def span(self) -> DateRange | None:
        if not self.transactions:
            return None
        return DateRange.spanning(transaction.date for transaction in self.transactions)


def plan_consolidation(formula: Formula) -> Consolidation:
    """Read every converted file. Rows are kept as is: identical rows are real transactions."""
    originals = store.converted_files(formula.outpath, formula.outprefix)
    transactions = [row for stored in originals for row in store.read_converted(stored.path)]
    return Consolidation(originals, transactions)


def consolidate(formula: Formula, consolidation: Consolidation) -> Path | None:
    """Write the merged file, then delete the originals. Returns the merged file, if any rows."""
    merged = None
    if consolidation.span is not None:
        merged = store.free_path(
            formula.outpath, formula.outprefix, consolidation.span, store.CONVERTED_SUFFIX
        )
        ynab_csv.write(merged, sorted(consolidation.transactions, key=lambda transaction: transaction.date))
    for stored in consolidation.originals:
        stored.path.unlink()
    return merged
