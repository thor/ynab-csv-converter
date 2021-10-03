import re
import locale
from collections import namedtuple

NordnetLine = namedtuple('NordnetLine', ['line_id', 'bogf_date', 'trns_date', 'val_date', 'portfolio_id',
                                         'trns_type', 'stock_name', 'instr_type', 'isin', 'quantity', 'price',
                                         'interest', 'fee', 'fee_currency', 'amount', 'currency',
                                         'buy_price', 'result', 'total_qty', 'saldo', 'exch_rate', 'trns_text',
                                         'shred_date', 'slip_number', 'verification_number', 'brkr_fee',
                                         'brkr_fee_currency',
                                         ])

thousands = r' '
date_pattern = r'^\d{4}-\d{2}-\d{2}$'
optional_date_pattern = r'^(\d{4}-\d{2}-\d{2}|)$'
amount_pattern = r'\d{1,3}(' + thousands + r'\d{3})*(,\d{1,})?'
all_amount_pattern = r'^-?' + amount_pattern + r'$'
pos_amount_pattern = r'^' + amount_pattern + r'$'
opt_amount_pattern = r'(' + amount_pattern + r')?$'
column_patterns = {'line_id':     r'^\d{9,}$',
                   'bogf_date':   date_pattern,
                   'trns_date':   date_pattern,
                   'val_date':    date_pattern,
                   'trns_type':   r'^.+$',
                   'stock_name':  r'^.*$',
                   'instr_type':  r'^.*$',
                   'isin':        r'^.*$',
                   'quantity':    pos_amount_pattern,
                   'price':       pos_amount_pattern,
                   'interest':    pos_amount_pattern,
                   'fee':         pos_amount_pattern,
                   'amount':      all_amount_pattern,
                   'currency':    r'^[A-Z]{3}$',
                   'buy_price':   pos_amount_pattern,
                   'result':      all_amount_pattern,
                   'total_qty':   all_amount_pattern,
                   'saldo':       all_amount_pattern,
                   'exch_rate':   pos_amount_pattern,
                   'trns_text':   r'^.*$',
                   'shred_date':  optional_date_pattern,
                   'slip_number': r'^\d*$',
                   'verification_number': r'^\d{8,}$',
                   'brkr_fee':    opt_amount_pattern,
                   'brkr_fee_currency':  r'^.*$',
                   }
column_patterns = {column: re.compile(regex) for column, regex in column_patterns.items()}
txn_date_descends = True


def to_float(amount):
    return locale.atof(amount.replace(' ', ''))


def getlines(path):
    import csv
    import datetime
    import locale
    from . import validate_line
    from .ynab import YnabLine

    locale.setlocale(locale.LC_ALL, '')
    global thousands
    thousands = locale.localeconv()['grouping']

    with open(path, 'r', encoding='utf-16') as handle:
        transactions = csv.reader(handle, delimiter='\t', quoting=csv.QUOTE_MINIMAL)
        conv = {'EUR': 7.46, 'USD': 6.68, 'DKK': 1, 'NOK': 1}
        # Skip headers
        next(transactions)
        for raw_line in transactions:
            if len(raw_line) == 0:
                # export may contain empty lines
                continue
            try:
                line = NordnetLine(*raw_line)
                validate_line(line, column_patterns)

                date = datetime.datetime.strptime(line.bogf_date, '%Y-%m-%d')
                exch_rate = to_float(line.exch_rate)
                local_price = to_float(line.price) * exch_rate
                if 'aktie' in line.instr_type.lower():
                    payee = '{action} {code}'.format(action=line.trns_type.capitalize(), code=line.stock_name)
                    memo = f'{line.quantity} stk. til {line.currency} {local_price}'
                    if exch_rate != 0:
                        memo += f' (veksl. {line.exch_rate})'
                else:
                    payee = line.trns_type.capitalize()
                    memo = ''
                category = ''
                amount = round(locale.atof(line.amount.replace(' ', '')) * conv[line.currency], 2)
                if amount > 0:
                    outflow = 0.0
                    inflow = abs(amount)
                else:
                    outflow = abs(amount)
                    inflow = 0.0
            except Exception:
                import sys
                msg = ("There was a problem on line {line} in {path}\n"
                       .format(line=transactions.line_num, path=path))
                sys.stderr.write(msg)
                raise

            yield YnabLine(date, payee, category, memo, outflow, inflow)
