"""
Parsing the "last transactions" CSV-export from OBOS Bank in Norway.

The module makes a lot of assumptions, and is hardly battletested, except for on my own transactions.
As such it should be used on a very, small set of transactions initially.
Once you've established some trust and confirmed that my assumptions also hold for your use-case please feel free to
help tidy up or come with suggestions.

This module is to be considered untested, unstable, alpha, et cetera.

.. module:: obos_recent

.. moduleauthor:: Thor K. Høgås <thor at roht no>


"""

import csv
import datetime
import locale
import re
from collections import namedtuple

from .. import validate_line
from ..ynab import YnabLine

ObosLine = namedtuple('ObosLine', ['date', 'type', 'text', 'amount'])
amount_pattern = r'^-?\d{1,}(\.\d{3})*(.\d{1,2})?$'
date_pattern = r'^\d{2}\.\d{2}\.\d{4}'
short_date_pattern = r'(?P<date>\d{2}\.\d{2})'
short_date_format = r'%d.%m'
column_patterns = {'date': date_pattern,
                   'type': r'^.+$',
                   'text': r'^.+$',
                   'amount': amount_pattern
                   }
column_patterns = {column: re.compile(regex) for column, regex in column_patterns.items()}

txn_date_descends = False

visa_card_pattern = r'(?P<card>^\*\d{4} )'
visa_start_pattern = fr'{visa_card_pattern} {short_date_pattern}'
visa_cost_pattern = r'(?P<currency>\w{3}) (?P<amount>\d{1,}\.\d{1,2})'
visa_payee_pattern = r'(?P<payee>.*?)( Kurs: (?P<rate>\d*\.\d*)|$)'


def getlines(path):
    with open(path, 'r', encoding='utf-8-sig') as handle:
        transactions = csv.reader(handle, delimiter="\t", quotechar='"',
                                  quoting=csv.QUOTE_ALL)
        locale.setlocale(locale.LC_ALL, 'nb_NO.UTF-8')

        # Skip header
        next(transactions)

        processors = {
            'Innbetaling': [
                try_improve_incoming_transaction
            ],
            'Overføring': [
                try_improve_incoming_transaction
            ],
            'Vipps overføring': [
                try_improve_from_vipps
            ],
            'Varekjøp': [
                try_improve_date,
                try_improve_from_purchase
            ],
            'AvtaleGiro': [],
            'eFaktura': [],
            'Betaling': []
        }
        [x.append(try_improve_with_memo) for x in processors.values()]

        for raw_line in transactions:
            try:
                line = ObosLine(*raw_line)
                validate_line(line, column_patterns)
                result = {'date': datetime.datetime.strptime(line.date, '%d.%m.%Y'),
                          'payee': None, 'category': "",
                          'memo': "", 'outflow': 0.0, 'inflow': 0.0}

                amount = locale.atof(line.amount)
                result.update({
                    'outflow': 0.0 if amount > 0 else -amount,
                    'inflow': 0.0 if amount < 0 else amount,
                })

                for improvement_function in processors[line.type]:
                    improvement_function(result, line)

            except Exception as e:
                import sys
                msg = ("There was a problem on line {line} in {path}, Python line {line_code}\n"
                       .format(line=transactions.line_num, path=path, line_code=sys.exc_info()[2].tb_lineno))
                sys.stderr.write(raw_line[2] + "\n")
                sys.stderr.write(msg)
                raise e

            yield YnabLine(**result)


def try_improve_date(output: dict, input: ObosLine):
    match_actual_date = re.search(fr'{visa_card_pattern}? {short_date_pattern}', input.text)
    if match_actual_date:
        payment_date = datetime.datetime.strptime(match_actual_date['date'], short_date_format)
        output_year: datetime.datetime.year = output['date'].year
        payment_date = payment_date.replace(year=output_year)

        # If the month is "into" the year, then it's the previous year, otherwise choo-choo
        # NOTE: This leaves other edgecases, but covers the majority
        if payment_date > output['date']:
            payment_date = payment_date.replace(year=output_year - 1)
        elif payment_date == output['date']:
            return

        output['date'] = payment_date


def try_improve_from_purchase(output: dict, input: ObosLine):
    if input.type != "Varekjøp":
        return

    payment_pattern = fr'({visa_card_pattern} )?{short_date_pattern} ({visa_cost_pattern} )?{visa_payee_pattern}'
    payment = re.search(payment_pattern, input.text)

    output['payee'] = payment['payee']
    if payment['card'] and payment['currency'] and payment['currency'] != 'NOK':
        output['memo'] = f"Valuta: {payment['amount']} {payment['currency']} ved {payment['rate']}"


def try_improve_from_vipps(output: dict, input: ObosLine):
    output['payee'] = "Vipps"


def try_improve_incoming_transaction(output: dict, input: ObosLine):
    if output['inflow'] > 0:
        output['category'] = "To be budgeted"
    pass


def try_improve_with_memo(output: dict, input: ObosLine):
    meta_pattern = r'(?P<type>Nettgiro fra|Fra|Til|Betalt): (?P<target>.*?)(?= (Fra|Til|Betalt)|$)'
    payee_keys = ('Til', 'Fra', 'Nettgiro fra')

    # Ordinary purchases don't need any of these
    if input.type == "Varekjøp":
        return

    # Vipps has a dedicated payee
    if output['payee'] != "Vipps":
        output['memo'] += f"{input.type} "

    if input.type == "AvtaleGiro":
        output['payee'] = re.sub(meta_pattern, "", input.text)
        return

    # Go through each Key: value entry in the text field and add them
    for match in re.finditer(meta_pattern, input.text):
        meta = match.groupdict()
        key, value = meta['type'], meta['target']
        if key in payee_keys and not output['payee']:
            output['payee'] = value
            continue

        output['memo'] += f" {key}: {value}"
