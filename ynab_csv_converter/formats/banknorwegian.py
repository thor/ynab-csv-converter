import csv
import locale
import re
from collections import namedtuple
from decimal import Decimal
from datetime import datetime

import pandas as pd
from ynab_csv_converter.formats import validate_line
from ynab_csv_converter.formats.ynab import YnabLine

NorwegianRow = namedtuple('NorwegianRow', ["date", "payee", "type", "currency_amount", "currency_rate", "currency", "amount", "merchant_area", "merchant_category", "book_date", "value_date"])

amount_pattern = r'^-?\d{1,}(\.\d{3})*(.\d{1,2})?$'
date_pattern = r'^\d{2}\.\d{2}\.\d{4}'
short_date_pattern = r'(?P<date>\d{2}\.\d{2})'
short_date_format = r'%d.%m'
txn_date_descends = False
visa_card_pattern = r'(?P<card>^\*\d{4} )'
visa_start_pattern = fr'{visa_card_pattern} {short_date_pattern}'
visa_cost_pattern = r'(?P<currency>\w{3}) (?P<amount>\d{1,}\.\d{1,2})'
visa_payee_pattern = r'(?P<payee>.*?)( Kurs: (?P<rate>\d*\.\d*)|$)'


def is_avtalegiro(input_line):
    """ Check if it's an AvtaleGiro transaction (automatic invoice) """
    return input_line.type in ('AvtaleGiro', 'AVTGI', 'IAVTG')


def is_purchase(input_line):
    """ Check if it's a purchase transaction """
    return input_line.type in ('Varekjøp', 'VARER', 'VISA VARE')


def is_stocks(input_line):
    """ Check if it's a type of "verdipapir" (stocks or similarly) """
    return input_line.type in ('VPAPIR')


def try_improve_date(output: dict, input: namedtuple):
    match_actual_date = re.search(fr'{visa_card_pattern}? {short_date_pattern}', input.text)
    if match_actual_date:
        payment_date = datetime.strptime(match_actual_date['date'], short_date_format)
        output_year: datetime.year = output['date'].year
        payment_date = payment_date.replace(year=output_year)

        # If the month is "into" the year, then it's the previous year, otherwise choo-choo
        # NOTE: This leaves other edgecases, but covers the majority
        if payment_date > output['date']:
            payment_date = payment_date.replace(year=output_year - 1)
        elif payment_date == output['date']:
            return

        output['date'] = payment_date


def try_improve_from_purchase(output: dict, input: namedtuple):
    payment_pattern = fr'({visa_card_pattern} )?{short_date_pattern} ({visa_cost_pattern} )?{visa_payee_pattern}'
    payment = re.search(payment_pattern, input.text)

    output['payee'] = payment['payee']
    if payment['card'] and payment['currency'] and payment['currency'] != 'NOK':
        output['memo'] = f"Valuta: {payment['amount']} {payment['currency']} ved {payment['rate']}"


def try_improve_from_vipps(output: dict, input: namedtuple):
    output['payee'] = "Vipps"


def try_improve_incoming_transaction(output: dict, input: namedtuple):
    if output['inflow'] > 0:
        output['category'] = "To be budgeted"
    pass


def try_add_account_information(output: dict, input: namedtuple):
    if not input.account:
        return

    output['memo'] += f" ({input.account})"


def try_improve_with_memo(output: dict, input: namedtuple):
    meta_pattern = r'(?P<type>Nettgiro til|Nettgiro fra|Fra|Til|Betalt): (?P<target>.*?)(?= (Fra|Til|Betalt)|$)'
    payee_keys = ('Til', 'Fra', 'Nettgiro fra', 'Nettgiro til')

    # Go through each Key: value entry in the text field and add them
    meta_matches = list(re.finditer(meta_pattern, input.text))

    # Ordinary purchases don't need any of these
    if is_purchase(input):
        return

    # Vipps has a dedicated payee
    if output['payee'] != "Vipps":
        output['memo'] += f"{input.type.lower().capitalize()}"

    if is_avtalegiro(input):
        output['memo'] = "AvtaleGiro"

    if is_stocks(input):
        output['memo'] = "Verdipapir(er)"

    if (is_avtalegiro(input) or is_stocks(input)) and not meta_matches:
        output['payee'] = re.sub(meta_pattern, "", input.text)
        return

    for meta in (x.groupdict() for x in meta_matches):
        key, value = meta['type'], meta['target']
        if key in payee_keys and not output['payee']:
            output['payee'] = value
            continue

        output['memo'] += f" {key}: {value}"


def getlines(path: str):
    # Load the transactions
    with open(path, 'r', encoding='utf-8-sig') as handle:
        transactions = csv.reader(handle, delimiter=',', quotechar='"',
                                  quoting=csv.QUOTE_ALL)
        locale.setlocale(locale.LC_ALL, 'nb_NO.UTF-8')

        next(transactions)

        for row in transactions:
            row = NorwegianRow(*row)
            try:
                result = {'date': datetime.strptime(row.date, '%Y/%m/%d'),
                          'payee': row.payee, 'category': "",
                          'memo': row.merchant_category, 'outflow': 0.0, 'inflow': 0.0}

                amount = Decimal(row.amount)
                result.update({
                    'outflow': 0.0 if amount > 0 else -amount,
                    'inflow': 0.0 if amount < 0 else amount,
                })

                if amount > 0:
                    result['memo'] = ""

                if row.currency != 'NOK':
                    result['memo'] += f" {row.currency_amount} {row.currency}"

            except Exception as e:
                import sys
                msg = ("There was a problem on line {line} in {path}, Python line {line_code}\n"
                       .format(line=transactions.line_num, path=path, line_code=sys.exc_info()[2].tb_lineno))
                sys.stderr.write(msg)
                raise e

            yield YnabLine(**result)
