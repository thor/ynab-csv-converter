from datetime import date
from decimal import Decimal

import pytest

from ynab_csv_converter.providers.base import ParseError
from ynab_csv_converter.providers.obos import archive, recent
from ynab_csv_converter.transaction import Transaction

RECENT = [
    ["Dato", "Type", "Tekst", "Beløp"],
    ["05.03.2024", "Innbetaling", "Fra: Ola Nordmann", "1500,00"],
    ["05.03.2024", "Overføring", "Til: Sparekonto", "-200,00"],
    ["06.03.2024", "Vipps overføring", "Til: Kari Nordmann", "-150,00"],
    ["07.03.2024", "Varekjøp", "*1234  04.03 EUR 12.50 CAFE PARIS Kurs: 11.52", "-144,00"],
    ["07.03.2024", "Varekjøp", "*1234  05.03 NOK 99.00 REMA 1000", "-99,00"],
    ["07.03.2024", "Varekjøp", "*1234  05.03 EUR 10.00 SHOP", "-115,00"],
    ["07.03.2024", "Varekjøp", "06.03 KIWI OSLO", "-45,50"],
    ["02.01.2024", "Varekjøp", "*1234  28.12 KIWI OSLO", "-80,00"],
    ["08.03.2024", "AvtaleGiro", "Hafslund Strøm", "-650,00"],
    ["08.03.2024", "AvtaleGiro", "Til: Telenor Betalt: 08.03.24", "-399,00"],
    ["09.03.2024", "eFaktura", "Til: Fjordkraft Betalt: 09.03.24", "-512,30"],
    ["09.03.2024", "Betaling", "Husleie mars", "-9000,00"],
]

ARCHIVE = [
    ["Bokført", "Rentedato", "Type", "Tekst", "Beløp", "Ref", "Konto"],
    ["25.02.2024", "25.02.2024", "LØNN", "Fra: ACME AS", "35000,00", "1", ""],
    ["26.02.2024", "26.02.2024", "GIRO", "Fra: Skatteetaten", "1200,00", "2", ""],
    ["26.02.2024", "26.02.2024", "OVERFØRT", "Til: Sparekonto", "-500,00", "3", "1234.56.78901"],
    ["27.02.2024", "27.02.2024", "STRAKSBET", "Til: Per Hansen", "-75,00", "4", ""],
    ["27.02.2024", "27.02.2024", "StraksOvf", "Fra: Kari Nordmann", "250,00", "5", ""],
    ["28.02.2024", "28.02.2024", "VARER", "*1234  26.02 KIWI OSLO", "-45,00", "6", "1234.56.78901"],
    ["28.02.2024", "28.02.2024", "VISA VARE", "*1234  25.02 USD 20.00 AMAZON Kurs: 10.80", "-216", "7", ""],
    ["29.02.2024", "29.02.2024", "AVTGI", "Hafslund Strøm", "-650,00", "8", ""],
    ["29.02.2024", "29.02.2024", "IAVTG", "Til: Telenor Betalt: 29.02.24", "-399,00", "9", ""],
    ["29.02.2024", "29.02.2024", "E-FAKTURA", "Til: Fjordkraft", "-512,30", "10", ""],
    ["01.03.2024", "01.03.2024", "NETTGIRO", "Nettgiro til: Ola Betalt: 01.03.24", "-100,00", "11", ""],
    ["01.03.2024", "01.03.2024", "NETTGIRO", "Fra: Brukskonto Til: Kari Nordmann", "-200,00", "12", ""],
    ["02.03.2024", "02.03.2024", "MOBILGIRO", "Til: Elkjøp", "-1999,00", "13", ""],
    ["03.03.2024", "03.03.2024", "VPAPIR", "KLP AksjeNorge", "-1000,00", "14", ""],
    ["03.03.2024", "03.03.2024", "VPAPIR", "Til: Nordnet", "-500,00", "15", ""],
    ["04.03.2024", "04.03.2024", "KREDITRTE", "Kreditrente", "3,21", "16", ""],
]


def write_export(tmp_path, rows):
    path = tmp_path / "obos.csv"
    path.write_text("".join("\t".join(row) + "\n" for row in rows), encoding="iso8859-1")
    return path


def test_parses_recent_export(tmp_path):
    assert recent.provider.read_transactions(write_export(tmp_path, RECENT)) == [
        Transaction(date(2024, 3, 5), "Ola Nordmann", Decimal("1500.00"), "Innbetaling", "To be budgeted"),
        Transaction(date(2024, 3, 5), "Sparekonto", Decimal("-200.00"), "Overføring"),
        Transaction(date(2024, 3, 6), "Vipps", Decimal("-150.00"), " Til: Kari Nordmann"),
        Transaction(date(2024, 3, 4), "CAFE PARIS", Decimal("-144.00"), "Valuta: 12.50 EUR ved 11.52"),
        Transaction(date(2024, 3, 5), "REMA 1000", Decimal("-99.00")),
        # No "Kurs:" in the text: legacy wrote the missing rate as "None". Kept for dedup stability.
        Transaction(date(2024, 3, 5), "SHOP", Decimal("-115.00"), "Valuta: 10.00 EUR ved None"),
        # No leading space before the date, so the date regex misses it and the booking date stays.
        Transaction(date(2024, 3, 7), "KIWI OSLO", Decimal("-45.50")),
        Transaction(date(2023, 12, 28), "KIWI OSLO", Decimal("-80.00")),
        Transaction(date(2024, 3, 8), "Hafslund Strøm", Decimal("-650.00"), "AvtaleGiro"),
        Transaction(date(2024, 3, 8), "Telenor", Decimal("-399.00"), "AvtaleGiro Betalt: 08.03.24"),
        Transaction(date(2024, 3, 9), "Fjordkraft", Decimal("-512.30"), "Efaktura Betalt: 09.03.24"),
        Transaction(date(2024, 3, 9), "", Decimal("-9000.00"), "Betaling"),
    ]


def test_parses_archive_export(tmp_path):
    account = "(1234.56.78901)"
    assert archive.provider.read_transactions(write_export(tmp_path, ARCHIVE)) == [
        Transaction(date(2024, 2, 25), "ACME AS", Decimal("35000.00"), "Lønn", "To be budgeted"),
        Transaction(date(2024, 2, 26), "Skatteetaten", Decimal("1200.00"), "Giro", "To be budgeted"),
        Transaction(date(2024, 2, 26), "Sparekonto", Decimal("-500.00"), f"Overført {account}"),
        Transaction(date(2024, 2, 27), "Per Hansen", Decimal("-75.00"), "Straksbet"),
        Transaction(date(2024, 2, 27), "Vipps", Decimal("250.00"), " Fra: Kari Nordmann"),
        Transaction(date(2024, 2, 26), "KIWI OSLO", Decimal("-45.00"), f" {account}"),
        Transaction(date(2024, 2, 25), "AMAZON", Decimal("-216.00"), "Valuta: 20.00 USD ved 10.80"),
        Transaction(date(2024, 2, 29), "Hafslund Strøm", Decimal("-650.00"), "AvtaleGiro"),
        Transaction(date(2024, 2, 29), "Telenor", Decimal("-399.00"), "AvtaleGiro Betalt: 29.02.24"),
        Transaction(date(2024, 2, 29), "Fjordkraft", Decimal("-512.30"), "E-faktura"),
        Transaction(date(2024, 3, 1), "Ola", Decimal("-100.00"), "Nettgiro Betalt: 01.03.24"),
        Transaction(date(2024, 3, 1), "Brukskonto", Decimal("-200.00"), "Nettgiro Til: Kari Nordmann"),
        Transaction(date(2024, 3, 2), "Elkjøp", Decimal("-1999.00"), "Mobilgiro"),
        Transaction(date(2024, 3, 3), "KLP AksjeNorge", Decimal("-1000.00"), "Verdipapir(er)"),
        Transaction(date(2024, 3, 3), "Nordnet", Decimal("-500.00"), "Verdipapir(er)"),
        Transaction(date(2024, 3, 4), "", Decimal("3.21"), "Kreditrte"),
    ]


def test_purchase_on_leap_day(tmp_path):
    # Legacy crashed here: it parsed "29.02" without a year, which defaults to 1900.
    rows = [ARCHIVE[0], ["01.03.2024", "01.03.2024", "VARER", "*1234  29.02 KIWI OSLO", "-45,00", "1", ""]]
    [transaction] = archive.provider.read_transactions(write_export(tmp_path, rows))
    assert transaction.date == date(2024, 2, 29)


def test_rejects_unknown_type(tmp_path):
    rows = [ARCHIVE[0], ["01.03.2024", "01.03.2024", "UKJENT", "Noe", "-1,00", "1", ""]]
    with pytest.raises(ParseError, match="Unknown transaction type 'UKJENT'"):
        archive.provider.read_transactions(write_export(tmp_path, rows))
