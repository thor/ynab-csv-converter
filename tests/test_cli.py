import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ynab_csv_converter import ynab_csv
from ynab_csv_converter.cli import app

JULY = (
    '"31-07-2026";"31-07-2026";"Netto";"-1.234,50";"10.000,00"\n'
    '"15-07-2026";"15-07-2026";"Kaffe";"-35,00";"11.234,50"\n'
    '"15-07-2026";"15-07-2026";"Kaffe";"-35,00";"11.269,50"\n'
    '"01-07-2026";"01-07-2026";"Løn";"25.000,00";"11.304,50"\n'
)
AUGUST = (
    '"31-08-2026";"31-08-2026";"Netto";"-99,00";"0,00"\n"01-08-2026";"01-08-2026";"Bus";"-24,00";"99,00"\n'
)
SEPTEMBER = (
    '"30-09-2026";"30-09-2026";"Netto";"-10,00";"0,00"\n"01-09-2026";"01-09-2026";"Bus";"-24,00";"10,00"\n'
)

runner = CliRunner()


@pytest.fixture
def home(tmp_path) -> Path:
    formula = (
        f"format: sparekassen\noutpath: {tmp_path}/out\narchivepath: {tmp_path}/archive\noutprefix: spk\n"
    )
    (tmp_path / "formula.yml").write_text(formula)
    (tmp_path / "out").mkdir()
    (tmp_path / "archive").mkdir()
    return tmp_path


def export(home: Path, name: str, content: str) -> str:
    path = home / name
    path.write_text(content, encoding="utf-8-sig")
    return str(path)


def run(home: Path, *args: str, input: str | None = None):
    command, *rest = args
    return runner.invoke(app, [command, str(home / "formula.yml"), *rest], input=input)


def names(folder: Path) -> list[str]:
    return sorted(path.name for path in folder.iterdir()) if folder.exists() else []


def test_first_import(home):
    result = run(home, "convert", export(home, "july.csv", JULY), input="y\n")

    assert result.exit_code == 0, result.output
    assert f"First import for this formula (nothing in {(home / 'out').resolve()} yet)." in result.output
    assert "4 read, 4 new, 0 already converted" in result.output
    assert "Kaffe" in result.output
    assert names(home / "out") == ["spk-20260731-20260701.csv"]
    assert names(home / "archive") == ["spk-20260731-20260701.csv"]
    assert not (home / "july.csv").exists()
    assert len(ynab_csv.read(home / "out" / "spk-20260731-20260701.csv")) == 4


def test_reimport_finds_only_duplicates(home):
    run(home, "convert", "-y", export(home, "july.csv", JULY))

    result = run(home, "convert", export(home, "july.csv", JULY), input="y\n")

    assert result.exit_code == 0, result.output
    assert "4 read, 0 new, 4 already converted" in result.output
    assert "Already imported" in result.output
    assert "[y/N]" in result.output
    assert "on dates already imported" not in result.output
    assert names(home / "out") == ["spk-20260731-20260701.csv"]
    assert names(home / "archive") == ["spk-20260731-20260701-1.csv", "spk-20260731-20260701.csv"]


def test_reimport_is_skipped_by_default(home):
    run(home, "convert", "-y", export(home, "july.csv", JULY))

    result = run(home, "convert", export(home, "july.csv", JULY), input="\n")

    assert result.exit_code == 0, result.output
    assert "Skipped" in result.output
    assert (home / "july.csv").exists()
    assert names(home / "archive") == ["spk-20260731-20260701.csv"]


def test_new_rows_on_imported_dates_warn_but_default_to_yes(home):
    run(home, "convert", "-y", export(home, "july.csv", JULY))
    changed = JULY.replace("Netto", "NETTO 1234") + AUGUST

    result = run(home, "convert", export(home, "july-aug.csv", changed), input="\n")

    assert result.exit_code == 0, result.output
    assert "1 new row falls on dates already imported. Check they are not duplicates with changed text." in (
        result.output
    )
    assert "[Y/n]" in result.output
    assert not (home / "july-aug.csv").exists()


def test_one_of_two_identical_rows_is_new(home):
    run(
        home,
        "convert",
        "-y",
        export(home, "july.csv", JULY.replace('"15-07-2026";"15-07-2026";"Kaffe"', "", 1)),
    )
    run(home, "convert", "-y", export(home, "july.csv", JULY))

    converted = [t for path in (home / "out").iterdir() for t in ynab_csv.read(path)]
    assert sum(t.payee == "Kaffe" for t in converted) == 2


def test_later_month_leaves_gap_and_confirm_defaults_to_no(home):
    run(home, "convert", "-y", export(home, "july.csv", JULY))

    result = run(home, "convert", export(home, "september.csv", SEPTEMBER), input="\n")

    assert result.exit_code == 0, result.output
    assert (
        "Missing 2026-08-01 to 2026-08-31: last import ends 2026-07-31, this file starts 2026-09-01"
        in result.output
    )
    assert "[y/N]" in result.output
    assert "Skipped" in result.output
    assert (home / "september.csv").exists()
    assert names(home / "out") == ["spk-20260731-20260701.csv"]


def test_declined_month_counts_as_missing_for_the_next_file(home):
    run(home, "convert", "-y", export(home, "july.csv", JULY))
    august, september = export(home, "aug.csv", AUGUST), export(home, "sep.csv", SEPTEMBER)

    result = run(home, "convert", august, september, input="n\n\n")

    assert result.exit_code == 0, result.output
    september_part = result.output[result.output.index("sep.csv") :]
    assert "Missing 2026-08-01 to 2026-08-31" in september_part
    assert "[y/N]" in september_part
    assert Path(august).exists() and Path(september).exists()


def test_yes_refuses_gap_and_writes_nothing(home):
    run(home, "convert", "-y", export(home, "july.csv", JULY))

    result = run(home, "convert", "-y", export(home, "september.csv", SEPTEMBER))

    assert result.exit_code == 1
    assert "--allow-gaps" in result.output
    assert (home / "september.csv").exists()
    assert names(home / "out") == ["spk-20260731-20260701.csv"]


def test_allow_gaps_converts(home):
    run(home, "convert", "-y", export(home, "july.csv", JULY))

    result = run(home, "convert", "-y", "--allow-gaps", export(home, "september.csv", SEPTEMBER))

    assert result.exit_code == 0, result.output
    assert names(home / "out") == ["spk-20260731-20260701.csv", "spk-20260930-20260901.csv"]


def test_consecutive_months_in_one_run_have_no_gap(home):
    run(home, "convert", "-y", export(home, "july.csv", JULY))

    result = run(home, "convert", "-y", export(home, "sep.csv", SEPTEMBER), export(home, "aug.csv", AUGUST))

    assert result.exit_code == 0, result.output
    assert "Missing" not in result.output
    assert result.output.index("aug.csv") < result.output.index("sep.csv")
    assert len(names(home / "out")) == 3


def test_dry_run_writes_nothing(home):
    source = export(home, "july.csv", JULY)

    result = run(home, "convert", "--dry-run", source)

    assert result.exit_code == 0, result.output
    assert "4 new" in result.output
    assert "Dry run: nothing written." in result.output
    assert Path(source).exists()
    assert names(home / "out") == [] and names(home / "archive") == []


def test_preview_is_a_dry_run_even_with_gaps(home):
    run(home, "convert", "-y", export(home, "july.csv", JULY))

    result = run(home, "preview", export(home, "september.csv", SEPTEMBER))

    assert result.exit_code == 0, result.output
    assert "Missing 2026-08-01 to 2026-08-31" in result.output
    assert (home / "september.csv").exists()


def test_long_preview_is_truncated(home):
    rows = "".join(
        f'"{day:02}-07-2026";"{day:02}-07-2026";"Shop {day}";"-1,00";"0,00"\n' for day in range(1, 31)
    )

    result = run(home, "preview", export(home, "july.csv", rows))

    assert "... 15 more" in result.output


def test_status(home):
    run(home, "convert", "-y", export(home, "july.csv", JULY))
    run(home, "convert", "-y", "--allow-gaps", export(home, "september.csv", SEPTEMBER))

    result = run(home, "status")

    assert result.exit_code == 0, result.output
    assert "Missing 2026-08-01 to 2026-08-31 (31 days)" in result.output
    days = (date.today() - date(2026, 9, 30)).days
    assert f"Last import ends 2026-09-30, {days} days ago." in result.output


def test_status_shows_gap_hidden_by_a_consolidated_file(home):
    (home / "archive").mkdir(exist_ok=True)
    (home / "archive" / "spk-20260203-20260201.csv").write_text("")
    (home / "archive" / "spk-20260310-20260310.csv").write_text("")
    (home / "out").mkdir(exist_ok=True)
    (home / "out" / "spk-20260310-20260201.csv").write_text("")

    result = run(home, "status")

    assert result.exit_code == 0, result.output
    assert "Missing 2026-02-04 to 2026-03-09 (34 days)" in result.output


def test_status_ignores_gaps_up_to_max_gap_days(home):
    for name in ["spk-20260710-20260701", "spk-20260720-20260712", "spk-20260731-20260725"]:
        (home / "archive" / f"{name}.csv").write_text("")
    (home / "archive" / "spk-20260930-20260901.csv").write_text("")

    result = run(home, "status")

    assert "2026-07-01 │ 2026-07-31" in result.output
    assert "Missing 2026-08-01 to 2026-08-31 (31 days)" in result.output
    assert "Missing 2026-07-11" not in result.output
    assert "Ignored 2 gaps of 7 days or less." in result.output


def test_status_pluralises_one_day(home):
    (home / "formula.yml").write_text((home / "formula.yml").read_text() + "max_gap_days: 0\n")
    (home / "archive" / "spk-20260701-20260701.csv").write_text("")
    (home / "archive" / "spk-20260703-20260703.csv").write_text("")

    result = run(home, "status")

    assert "Missing 2026-07-02 to 2026-07-02 (1 day)" in result.output


def test_status_without_imports(home):
    assert "No imports yet in" in run(home, "status").output


@pytest.mark.parametrize("command", ["status", "consolidate", "preview"])
def test_missing_folder_is_an_error_not_an_empty_history(home, command):
    (home / "archive").rmdir()
    args = [export(home, "july.csv", JULY)] if command == "preview" else []

    result = run(home, command, *args)

    assert result.exit_code == 1
    assert f"archivepath folder not found: {home / 'archive'}" in result.output


def test_consolidate(home):
    run(home, "convert", "-y", export(home, "july.csv", JULY))
    run(home, "convert", "-y", export(home, "aug.csv", AUGUST))

    result = run(home, "consolidate", input="y\n")

    assert result.exit_code == 0, result.output
    assert names(home / "out") == ["spk-20260831-20260701.csv"]
    merged = ynab_csv.read(home / "out" / "spk-20260831-20260701.csv")
    assert len(merged) == 6
    assert sum(t.payee == "Kaffe" for t in merged) == 2


def test_consolidate_empty_files(home):
    (home / "out").mkdir(exist_ok=True)
    (home / "out" / "spk-20260710-20260701.csv").write_text("Date,Payee,Category,Memo,Outflow,Inflow\n")
    (home / "out" / "spk-20260731-20260720.csv").write_text("Date,Payee,Category,Memo,Outflow,Inflow\n")

    result = run(home, "consolidate", "-y")

    assert result.exit_code == 0, result.output
    assert "Merge 2 files with 0 transactions:" in result.output
    assert "No transactions, removed 2 files." in result.output
    assert "None" not in result.output
    assert names(home / "out") == []


def test_consolidate_declined_changes_nothing(home):
    run(home, "convert", "-y", export(home, "july.csv", JULY))
    run(home, "convert", "-y", export(home, "aug.csv", AUGUST))

    result = run(home, "consolidate", input="n\n")

    assert result.exit_code == 0, result.output
    assert len(names(home / "out")) == 2


def test_consolidate_needs_two_files(home):
    run(home, "convert", "-y", export(home, "july.csv", JULY))

    assert "Nothing to consolidate: 1 converted file." in run(home, "consolidate", "-y").output


def test_providers():
    result = runner.invoke(app, ["providers"])

    assert "sparekassen" in result.output
    assert "Sparekassen Kronjylland" in result.output


def test_parse_error_is_one_clean_message(home):
    result = run(home, "convert", "-y", export(home, "bad.csv", '"31-07-2026";"x";"Netto";"abc";"0"\n'))

    assert result.exit_code == 1
    assert "bad.csv:1: Not an amount: 'abc'" in result.output
    assert "Traceback" not in result.output


def test_debug_shows_traceback(home):
    source = export(home, "bad.csv", '"31-07-2026";"x";"Netto";"abc";"0"\n')

    result = runner.invoke(app, ["--debug", "convert", "-y", str(home / "formula.yml"), source])

    assert result.exit_code == 1
    assert result.exception is not None


def test_bad_formula(home):
    formula = home / "formula.yml"
    formula.write_text(formula.read_text().replace("sparekassen", "nosuchbank"))

    result = run(home, "status")

    assert result.exit_code == 1
    assert f"{formula}: unknown format 'nosuchbank'" in result.output


def test_missing_file(home):
    result = run(home, "convert", str(home / "nope.csv"))

    assert result.exit_code == 1
    assert "nope.csv: file not found" in result.output


def test_runs_as_module():
    result = subprocess.run(
        [sys.executable, "-m", "ynab_csv_converter", "--help"], capture_output=True, text=True, check=True
    )

    assert "ynab-csv-converter" in result.stdout
