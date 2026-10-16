"""Turn bank exports into YNAB CSV files, skipping what was converted before.

Flow: `ImportBatch.read(formula, paths)`, then for each source `batch.plan(source)`,
`apply(formula, plan)` to write, and `batch.record(plan)` so later files in the
batch dedup against it. Preview is the same flow without `apply`.
"""

import csv
import re
import shutil
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from . import store, ynab_csv
from .coverage import DateRange, Gap, batch_gaps, count_covered, is_already_imported, span_of
from .formula import Formula
from .transaction import Transaction


class SourceError(Exception):
    pass


@dataclass(frozen=True)
class Source:
    path: Path
    transactions: list[Transaction]
    """Every transaction in the file, with the formula factor applied."""

    @property
    def span(self) -> DateRange | None:
        return span_of(self.transactions)


@dataclass(frozen=True)
class Plan:
    source: Source
    new: list[Transaction]
    gaps: list[Gap]
    first_import: bool
    already_imported: bool
    new_on_imported_dates: int
    """New rows dated inside existing coverage: late postings, or old rows whose text changed."""

    @property
    def duplicate_count(self) -> int:
        return len(self.source.transactions) - len(self.new)


@dataclass(frozen=True)
class Applied:
    converted: Path | None
    archived: Path


@dataclass
class ImportBatch:
    """Sources to import together, oldest first, with what is already converted."""

    formula: Formula
    sources: list[Source]
    existing_coverage: list[DateRange]
    converted: list[Transaction]
    declined: set[Path] = field(default_factory=set)

    @classmethod
    def read(cls, formula: Formula, paths: Iterable[Path]) -> "ImportBatch":
        sources = sorted(
            (read_source(formula, path) for path in _unique(paths)),
            key=lambda source: (source.span is None, source.span),
        )
        batch_span = span_of(transaction for source in sources for transaction in source.transactions)
        return cls(formula, sources, existing_coverage(formula), read_converted_in(formula, batch_span))

    @property
    def has_gaps(self) -> bool:
        return any(self._gaps().values())

    def plan(self, source: Source) -> Plan:
        span = source.span
        new = new_transactions(source.transactions, self.converted)
        return Plan(
            source=source,
            new=new,
            gaps=self._gaps().get(source.path, []),
            first_import=not self.existing_coverage and source is self.sources[0],
            already_imported=span is not None and is_already_imported(span, self.existing_coverage, len(new)),
            new_on_imported_dates=count_covered(
                (transaction.date for transaction in new), self.existing_coverage
            ),
        )

    def record(self, plan: Plan) -> None:
        """Count `plan` as converted, so later sources skip its transactions."""
        self.converted.extend(plan.new)

    def decline(self, source: Source) -> None:
        """Leave `source` out, so later sources no longer count on its dates."""
        self.declined.add(source.path)

    def _gaps(self) -> dict[Path, list[Gap]]:
        dated = [source for source in self.sources if source.span and source.path not in self.declined]
        spans = [source.span for source in dated]
        gaps = batch_gaps(spans, self.existing_coverage, self.formula.max_gap_days)
        return {source.path: source_gaps for source, source_gaps in zip(dated, gaps, strict=True)}


def read_source(formula: Formula, path: Path) -> Source:
    if not path.is_file():
        raise SourceError(f"{path}: file not found")
    try:
        transactions = formula.provider.read_transactions(path)
    except (ValueError, csv.Error) as error:
        raise SourceError(f"{path}: {error}") from error
    return Source(path, [transaction.scaled(formula.factor) for transaction in transactions])


def existing_coverage(formula: Formula) -> list[DateRange]:
    """Spans of archived exports.

    Converted files only count when the archive is empty: consolidate merges them into one
    file spanning everything, which would hide the holes in between.
    """
    stored = store.list_files(formula.archivepath, formula.outprefix) or store.converted_files(
        formula.outpath, formula.outprefix
    )
    return [file.span for file in stored]


def read_converted_in(formula: Formula, span: DateRange | None) -> list[Transaction]:
    """Rows of converted files whose name overlaps `span`. Others cannot be duplicates."""
    if span is None:
        return []
    files = [
        stored
        for stored in store.converted_files(formula.outpath, formula.outprefix)
        if stored.span.overlaps(span)
    ]
    return [transaction for stored in files for transaction in store.read_converted(stored.path)]


def new_transactions(incoming: Sequence[Transaction], converted: Iterable[Transaction]) -> list[Transaction]:
    """Transactions in `incoming` not already in `converted`.

    Counts matter: two identical rows where one was converted before leave one new row.
    """
    span = span_of(incoming)
    if span is None:
        return []
    remaining = Counter(t for t in converted if span.first <= t.date <= span.last)
    new = []
    for transaction in incoming:
        if remaining[transaction] > 0:
            remaining[transaction] -= 1
        else:
            new.append(transaction)
    return new


def apply(formula: Formula, plan: Plan) -> Applied:
    """Write new transactions, then move the source into the archive."""
    span = plan.source.span
    if span is None:
        raise SourceError(f"{plan.source.path}: no transactions, nothing to convert")

    converted = None
    if plan.new:
        formula.outpath.mkdir(parents=True, exist_ok=True)
        converted = store.free_path(
            formula.outpath, formula.outprefix, span_of(plan.new), store.CONVERTED_SUFFIX
        )
        ynab_csv.write(converted, plan.new)

    formula.archivepath.mkdir(parents=True, exist_ok=True)
    archived = store.free_path(
        formula.archivepath, formula.outprefix, span, _archive_suffix(plan.source.path)
    )
    shutil.move(plan.source.path, archived)
    return Applied(converted, archived)


def _archive_suffix(path: Path) -> str:
    """Keep the source suffix unless the store could not read it back, e.g. `.csv~`."""
    return path.suffix if re.fullmatch(r"\.\w+", path.suffix) else ""


def _unique(paths: Iterable[Path]) -> list[Path]:
    return list(dict.fromkeys(path.resolve() for path in paths))
