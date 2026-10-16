from decimal import Decimal
from pathlib import Path

import pytest

from ynab_csv_converter.formula import Formula, FormulaError, load_formula

BASE = "format: sparekassen\noutpath: out\narchivepath: archive\noutprefix: spk\n"


def write(tmp_path, text) -> Path:
    path = tmp_path / "formula.yml"
    path.write_text(text)
    return path


def test_loads_minimal_formula_with_defaults(tmp_path):
    formula = load_formula(write(tmp_path, BASE))

    assert formula == Formula(
        path=tmp_path / "formula.yml",
        format="sparekassen",
        outpath=tmp_path / "out",
        archivepath=tmp_path / "archive",
        outprefix="spk",
        factor=Decimal(1),
        max_gap_days=7,
    )


def test_optional_settings(tmp_path):
    formula = load_formula(write(tmp_path, BASE + "factor: 7.45\nmax_gap_days: 3\n"))

    assert formula.factor == Decimal("7.45")
    assert formula.max_gap_days == 3


def test_expands_home_and_variables(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", "/home/me")
    monkeypatch.setenv("BANK", "/data/bank")
    text = "format: sparekassen\noutpath: ~/out\narchivepath: $BANK/archive\noutprefix: spk\n"

    formula = load_formula(write(tmp_path, text))

    assert formula.outpath == Path("/home/me/out")
    assert formula.archivepath == Path("/data/bank/archive")


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (BASE + "colour: red\n", "unknown setting(s): colour"),
        ("format: sparekassen\noutpath: out\narchivepath: archive\n", "missing setting(s): outprefix"),
        (BASE.replace("sparekassen", "nosuchbank"), "unknown format 'nosuchbank'. Known formats: "),
        (BASE + "factor: lots\n", "factor must be a number"),
        (BASE + "factor: true\n", "factor must be a number"),
        (BASE + "max_gap_days: 1.5\n", "max_gap_days must be a whole number"),
        (BASE + "max_gap_days: -1\n", "max_gap_days must be a whole number"),
        (BASE.replace("outprefix: spk", "outprefix: a/b"), "outprefix must be a file name prefix"),
        (BASE.replace("archivepath: archive", "archivepath: ./out"), "must be different folders"),
        ("", "expected a mapping"),
        ("- a\n- b\n", "expected a mapping"),
        ("format: [\n", "invalid YAML"),
    ],
)
def test_rejects_bad_formula_naming_the_file(tmp_path, text, message):
    path = write(tmp_path, text)

    with pytest.raises(FormulaError) as raised:
        load_formula(path)

    assert str(raised.value).startswith(f"{path}: ")
    assert message in str(raised.value)


def test_missing_file(tmp_path):
    with pytest.raises(FormulaError, match="file not found"):
        load_formula(tmp_path / "nope.yml")


def test_non_utf8_formula(tmp_path):
    path = tmp_path / "formula.yml"
    path.write_bytes(BASE.replace("out\n", "\u00d8konomi\n", 1).encode("latin-1"))

    with pytest.raises(FormulaError, match="not UTF-8 text"):
        load_formula(path)


def test_relative_paths_start_at_the_formula_folder(tmp_path, monkeypatch):
    monkeypatch.chdir("/")
    text = BASE.replace("outpath: out", "outpath: ../converted")

    formula = load_formula(write(tmp_path, text))

    assert formula.outpath == tmp_path.parent / "converted"
    assert formula.archivepath == tmp_path / "archive"


def test_require_folders(tmp_path):
    formula = load_formula(write(tmp_path, BASE))
    (tmp_path / "out").mkdir()

    with pytest.raises(FormulaError, match="archivepath folder not found"):
        formula.require_folders()

    (tmp_path / "archive").mkdir()
    formula.require_folders()
