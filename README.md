# YNAB CSV Converter

Converts bank exports to the YNAB CSV import format.

It remembers what you converted before, so each new file only holds transactions YNAB has not seen.
It shows a preview before writing anything, and warns when dates are missing between imports.

## Run

With [uv](https://docs.astral.sh/uv/) installed:

```sh
# Run without installing
uvx --from git+https://github.com/andsens/ynab-csv-converter ynab-csv-converter --help

# Or install it as a tool
uv tool install git+https://github.com/andsens/ynab-csv-converter

# Or from a checkout
uv run ynab-csv-converter --help
```

## Use

```sh
ynab-csv-converter preview sparekassen.yml ~/Downloads/export.csv   # see what would happen
ynab-csv-converter convert sparekassen.yml ~/Downloads/*.csv         # preview, confirm, convert
ynab-csv-converter status sparekassen.yml                            # imported dates, gaps, last import
ynab-csv-converter consolidate sparekassen.yml                       # merge converted files into one
ynab-csv-converter providers                                         # supported banks
```

`convert` shows each file before writing it: date range, new and duplicate rows, and the new transactions.
Then it asks. Afterwards the converted file lands in `outpath` and the bank export moves to `archivepath`.

Missing dates: if a file starts more than `max_gap_days` after your last import, or ends that long before the next one,
you see the exact missing span, and the prompt defaults to No:

```
! Missing 2026-08-01 to 2026-09-01: last import ends 2026-07-31, this file starts 2026-09-02
Convert sep.csv? [y/N]:
```

Files given together count as one batch, so converting August and September in one go is not a gap.
A file with nothing new whose dates are all imported already defaults to No.
New rows on dates already imported get a warning: they may be old rows whose payee or memo text changed.
Imported dates come from the archive, or from converted files when the archive is empty.
`--yes` skips the prompt but refuses to write when dates are missing, unless you add `--allow-gaps`.
`--dry-run` (or `preview`) writes nothing. `--debug` shows tracebacks.

## Formula

One YAML file per account:

```yml
format: sparekassen          # see `ynab-csv-converter providers`
outpath: ~/ynab/converted    # ~ and $VARS are expanded
archivepath: ~/ynab/archive  # must differ from outpath
outprefix: sparekassen-euro
factor: 7.45                 # optional, multiplies every amount (EUR -> DKK)
max_gap_days: 7              # optional, missing days allowed before warning
```

Files are named `<outprefix>-<newest date>-<oldest date>[-n].<suffix>`, so the newest sort last.
The archive keeps the export's own suffix, e.g. `.xlsx`.
A name that starts like one but does not match, e.g. `... copy.csv`, stops the run until you rename or remove it.

## Supported formats

| Key | Bank |
|---|---|
| `americanexpress` | American Express |
| `banknordik` | BankNordik |
| `banknorwegian` | Bank Norwegian |
| `danskebank` | Danske Bank (tab separated) |
| `eika` | Eika and other SDC portal banks |
| `hypovereinsbank` | HypoVereinsbank |
| `laanspar` | Lån & Spar |
| `nordnet` | Nordnet ("XLS compatible") |
| `obos.archive` | OBOS Bank, archive export |
| `obos.recent` | OBOS Bank, recent transactions export |
| `saxotradergo` | SaxoTraderGo account statement (.xlsx or .csv) |
| `sparebanken` | Sparebanken |
| `sparekassen` | Sparekassen Kronjylland |
| `starmoney` | StarMoney 13 |

## Add a provider

A provider is one module in `ynab_csv_converter/providers/`. It says how to read rows and how to turn a row into a
`Transaction`. See `sparekassen.py` for the smallest example:

```python
def parse_row(row: Row) -> Transaction | None:  # None skips the row
    booking_date, _transaction_date, text, amount, _balance = row
    return Transaction(
        date=parse_date(booking_date, "%d-%m-%Y"),
        payee=text,
        amount=parse_amount(amount, decimal_mark=",", thousands_mark="."),  # negative is outflow
    )


provider = Provider(
    key="sparekassen",
    name="Sparekassen Kronjylland",
    read_rows=csv_source(encoding="utf-8-sig", delimiter=";"),
    parse_row=parse_row,
)
```

Then list the module in `providers/__init__.py` and add a test in `tests/providers/`.

Row sources live in `providers/sources.py`:

- `csv_source(encoding=, delimiter=, skip_rows=, keyed_by_header=)`
- `xlsx_source(sheet=, skip_rows=, keyed_by_header=)` gives native cell values (datetime, float)
- `by_suffix({".csv": csv_source(...), ".xlsx": xlsx_source(...)})` picks one by file suffix

Parse errors report file, line, cause and the raw row.

## Changes in 2.0

Converted output matches 1.x for valid files, so dedup against old converted files keeps working. Exceptions:

- `americanexpress`: Outflow/Inflow columns are no longer negative. The net amount is unchanged and still dedups.
- `obos.recent` works. 1.x crashed on every row.
- Two identical transactions on the same day are both kept. 1.x dropped the second if the first was imported before.
- No system locales needed. Parsing no longer calls `setlocale`.

## Develop

```sh
uv run pytest
uv run ruff check . && uv run ruff format .
```
