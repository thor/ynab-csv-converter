"""Command line interface."""

import csv
import functools
from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from . import __version__
from .consolidate import consolidate as merge_converted
from .consolidate import plan_consolidation
from .convert import ImportBatch, Plan, SourceError, apply, existing_coverage
from .coverage import days_since, holes, merge
from .formula import Formula, FormulaError, load_formula
from .providers import PROVIDERS
from .providers.base import ParseError
from .store import StoreError

PREVIEW_ROWS = 15
USER_ERRORS = (FormulaError, ParseError, SourceError, StoreError, OSError, ValueError, csv.Error)

app = typer.Typer(
    help="Convert bank exports to YNAB CSV, skipping transactions you already imported.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_show_locals=False,
)
out = Console(highlight=False)
err = Console(stderr=True, highlight=False)
show_tracebacks = False

FormulaArg = Annotated[Path, typer.Argument(metavar="FORMULA", help="Formula YAML file.", show_default=False)]
FilesArg = Annotated[
    list[Path], typer.Argument(metavar="FILE...", help="Bank exports to convert.", show_default=False)
]
YesOption = Annotated[bool, typer.Option("--yes", "-y", help="Do not ask for confirmation.")]


def _show_version(value: bool):
    if value:
        out.print(f"ynab-csv-converter {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    debug: Annotated[bool, typer.Option("--debug", help="Show tracebacks on errors.")] = False,
    version: Annotated[
        bool, typer.Option("--version", callback=_show_version, is_eager=True, help="Show version.")
    ] = False,
):
    """Convert bank exports to YNAB CSV, skipping transactions you already imported."""
    global show_tracebacks
    show_tracebacks = debug


def friendly_errors(command):
    """Print known errors as red lines and exit 1. `--debug` shows the traceback instead."""

    @functools.wraps(command)
    def run(*args, **kwargs):
        try:
            return command(*args, **kwargs)
        except USER_ERRORS as error:
            if show_tracebacks:
                raise
            for line in str(error).splitlines():
                err.print(f"[red]{escape(line)}[/red]", soft_wrap=True)
            raise typer.Exit(1) from None

    return run


@app.command()
@friendly_errors
def convert(
    formula: FormulaArg,
    files: FilesArg,
    yes: YesOption = False,
    allow_gaps: Annotated[
        bool, typer.Option("--allow-gaps", help="With --yes, convert even when dates are missing.")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show what would happen, write nothing.")
    ] = False,
):
    """Convert bank exports to YNAB CSV and move them to the archive.

    Shows a preview per file first: new and duplicate rows, and missing dates.
    """
    run_import(formula, files, yes=yes, allow_gaps=allow_gaps, dry_run=dry_run)


@app.command()
@friendly_errors
def preview(formula: FormulaArg, files: FilesArg):
    """Show what convert would do. Writes nothing."""
    run_import(formula, files, yes=True, allow_gaps=True, dry_run=True)


def run_import(formula_path: Path, files: list[Path], *, yes: bool, allow_gaps: bool, dry_run: bool):
    formula = load_formula(formula_path)
    batch = ImportBatch.read(formula, files)
    refuse_gaps = yes and batch.has_gaps and not allow_gaps and not dry_run
    write = not dry_run and not refuse_gaps

    for source in batch.sources:
        plan = batch.plan(source)
        show_plan(formula, plan)
        if source.span is None:
            out.print("[yellow]No transactions found. Skipped.[/yellow]")
            continue
        if not write:
            batch.record(plan)
            continue
        if yes or typer.confirm(f"Convert {source.path.name}?", default=not plan.gaps):
            applied = apply(formula, plan)
            batch.record(plan)
            if applied.converted:
                out.print(
                    f"Wrote {len(plan.new)} transactions to {escape(str(applied.converted))}", soft_wrap=True
                )
            out.print(f"Archived to {escape(str(applied.archived))}", soft_wrap=True)
        else:
            batch.decline(source)
            out.print("Skipped.")

    if dry_run:
        out.print("\nDry run: nothing written.")
    if refuse_gaps:
        err.print("[red]Dates are missing, nothing written. Pass --allow-gaps to convert anyway.[/red]")
        raise typer.Exit(1)


def show_plan(formula: Formula, plan: Plan):
    source = plan.source
    out.rule(f"[bold]{escape(source.path.name)}[/bold]", align="left")
    provider = formula.provider
    out.print(f"Provider  {escape(provider.name)} ({provider.key})")
    if formula.factor != 1:
        out.print(f"Factor    {formula.factor}")
    if source.span:
        out.print(f"Dates     {source.span} ({source.span.days} days)")
    out.print(
        f"Rows      {len(source.transactions)} read, [green]{len(plan.new)} new[/green], "
        f"{plan.duplicate_count} already converted"
    )
    if plan.first_import:
        out.print("[blue]First import for this formula, nothing to compare against.[/blue]")
    for gap in plan.gaps:
        out.print(f"[bold yellow]! {gap}[/bold yellow]", soft_wrap=True)
    if plan.already_imported:
        out.print("[yellow]Already imported: every row is in the converted files.[/yellow]")
    if plan.new:
        out.print(transactions_table(plan.new))


def transactions_table(transactions) -> Table:
    table = Table(show_edge=False, pad_edge=False)
    table.add_column("Date")
    table.add_column("Payee", overflow="fold")
    table.add_column("Memo", overflow="fold")
    table.add_column("Amount", justify="right")
    for transaction in transactions[:PREVIEW_ROWS]:
        colour = "red" if transaction.amount < 0 else "green"
        table.add_row(
            str(transaction.date),
            escape(transaction.payee),
            escape(transaction.memo),
            f"[{colour}]{transaction.amount:.2f}[/{colour}]",
        )
    hidden = len(transactions) - PREVIEW_ROWS
    if hidden > 0:
        table.add_row("", f"[dim]... {hidden} more[/dim]", "", "")
    return table


@app.command()
@friendly_errors
def status(formula: FormulaArg):
    """Show which dates are imported, the gaps between them, and the newest date."""
    loaded = load_formula(formula)
    coverage = merge(existing_coverage(loaded))
    if not coverage:
        out.print("No imports yet.")
        return

    table = Table(title="Imported dates", title_justify="left", show_edge=False, pad_edge=False)
    table.add_column("From")
    table.add_column("To")
    table.add_column("Days", justify="right")
    for block in coverage:
        table.add_row(str(block.first), str(block.last), str(block.days))
    out.print(table)

    for hole in holes(coverage):
        style = "bold yellow" if hole.days > loaded.max_gap_days else "dim"
        out.print(f"[{style}]Missing {hole} ({hole.days} days)[/{style}]")

    newest = coverage[-1].last
    out.print(f"Last import ends {newest}, {days_since(newest, date.today())} days ago.")


@app.command()
@friendly_errors
def consolidate(formula: FormulaArg, yes: YesOption = False):
    """Merge all converted files of a formula into one file."""
    loaded = load_formula(formula)
    plan = plan_consolidation(loaded)
    if len(plan.originals) < 2:
        out.print(f"Nothing to consolidate: {len(plan.originals)} converted file(s).")
        return

    out.print(f"Merge {len(plan.originals)} files with {len(plan.transactions)} transactions ({plan.span}):")
    for stored in plan.originals:
        out.print(f"  {escape(stored.path.name)}", soft_wrap=True)
    if not yes and not typer.confirm("Merge and delete the originals?", default=True):
        out.print("Nothing changed.")
        return
    merged = merge_converted(loaded, plan)
    out.print(f"Wrote {escape(str(merged))}, removed {len(plan.originals)} files.", soft_wrap=True)


@app.command()
def providers():
    """List supported banks and export formats."""
    table = Table(show_edge=False, pad_edge=False)
    table.add_column("Format")
    table.add_column("Name")
    for key, provider in sorted(PROVIDERS.items()):
        table.add_row(key, escape(provider.name))
    out.print(table)
