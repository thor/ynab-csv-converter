"""Formula files: which provider to use and where converted and archived files live.

Example:

    format: sparekassen
    outpath: ~/ynab/converted
    archivepath: $HOME/ynab/archive   # relative paths start at the formula's folder
    outprefix: sparekassen-euro
    factor: 7.45        # optional, multiplies every amount
    max_gap_days: 7     # optional, missing days tolerated before warning
"""

import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import yaml

from .providers import PROVIDERS, Provider

REQUIRED_KEYS = {"format", "outpath", "archivepath", "outprefix"}
OPTIONAL_KEYS = {"factor", "max_gap_days"}
DEFAULT_MAX_GAP_DAYS = 7


class FormulaError(Exception):
    def __init__(self, path: Path, message: str):
        self.path = path
        super().__init__(f"{path}: {message}")


@dataclass(frozen=True)
class Formula:
    path: Path
    format: str
    outpath: Path
    archivepath: Path
    outprefix: str
    factor: Decimal = Decimal(1)
    max_gap_days: int = DEFAULT_MAX_GAP_DAYS

    @property
    def provider(self) -> Provider:
        return PROVIDERS[self.format]

    def require_folders(self) -> None:
        """Fail on a missing folder. Treating it as empty would restart the import history."""
        for key, folder in (("outpath", self.outpath), ("archivepath", self.archivepath)):
            if not folder.is_dir():
                raise FormulaError(
                    self.path, f"{key} folder not found: {folder}\n  Fix the path, or create the folder."
                )


def load_formula(path: Path) -> Formula:
    try:
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except FileNotFoundError:
        raise FormulaError(path, "file not found") from None
    except UnicodeDecodeError:
        raise FormulaError(path, "not UTF-8 text") from None
    except yaml.YAMLError as error:
        raise FormulaError(path, f"invalid YAML: {error}") from error
    return parse_formula(path, data)


def parse_formula(path: Path, data: object) -> Formula:
    if not isinstance(data, dict):
        raise FormulaError(path, "expected a mapping of settings")

    unknown = sorted(set(data) - REQUIRED_KEYS - OPTIONAL_KEYS)
    if unknown:
        raise FormulaError(path, f"unknown setting(s): {', '.join(map(str, unknown))}")
    missing = sorted(REQUIRED_KEYS - set(data))
    if missing:
        raise FormulaError(path, f"missing setting(s): {', '.join(missing)}")

    outpath = _folder(path, "outpath", data["outpath"])
    archivepath = _folder(path, "archivepath", data["archivepath"])
    if outpath.resolve() == archivepath.resolve():
        # Archived bank exports would be read back as converted YNAB files.
        raise FormulaError(path, "outpath and archivepath must be different folders")

    return Formula(
        path=path,
        format=_format(path, data["format"]),
        outpath=outpath,
        archivepath=archivepath,
        outprefix=_prefix(path, data["outprefix"]),
        factor=_factor(path, data.get("factor", 1)),
        max_gap_days=_max_gap_days(path, data.get("max_gap_days", DEFAULT_MAX_GAP_DAYS)),
    )


def _format(path: Path, value: object) -> str:
    if value not in PROVIDERS:
        known = ", ".join(sorted(PROVIDERS))
        raise FormulaError(path, f"unknown format {value!r}. Known formats: {known}")
    return value


def _folder(path: Path, key: str, value: object) -> Path:
    if not isinstance(value, str) or not value or "\0" in value:
        raise FormulaError(path, f"{key} must be a folder path")
    folder = Path(os.path.expanduser(os.path.expandvars(value)))
    return Path(os.path.normpath(folder if folder.is_absolute() else path.absolute().parent / folder))


def _prefix(path: Path, value: object) -> str:
    if not isinstance(value, str) or not value or "/" in value or "\0" in value:
        raise FormulaError(path, "outprefix must be a file name prefix without '/'")
    return value


def _factor(path: Path, value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise FormulaError(path, f"factor must be a number, got {value!r}")
    return Decimal(str(value))


def _max_gap_days(path: Path, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise FormulaError(path, f"max_gap_days must be a whole number of days, got {value!r}")
    return value
