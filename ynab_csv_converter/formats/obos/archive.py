"""
Parsing the "last transactions" CSV-export from OBOS Bank in Norway.

The module makes a lot of assumptions, and is hardly battletested, except for on my own transactions.
As such it should be used on a very, small set of transactions initially.
Once you've established some trust and confirmed that my assumptions also hold for your use-case please feel free to
help tidy up or come with suggestions.

This module is to be considered untested, unstable, alpha, et cetera.

.. module:: obos_archive

.. moduleauthor:: Thor K. Høgås <thor at roht no>


"""

from collections import namedtuple

from ynab_csv_converter.formats.obos import getlines_shared
from . import amount_pattern, date_pattern, try_improve_date, try_improve_from_purchase, \
    try_improve_from_vipps, try_improve_incoming_transaction


def getlines(path):
    ObosArchiveLine = namedtuple('ObosLine', ['date', 'intdate', 'type', 'text', 'amount', 'ref', 'account'])
    column_patterns = {'date': date_pattern,
                       'intdate': date_pattern,
                       'type': r'^.+$',
                       'text': r'^.+$',
                       'amount': amount_pattern
                       }
    processors = {
        'LØNN': [
            try_improve_incoming_transaction
        ],
        'GIRO': [
            try_improve_incoming_transaction
        ],
        'OVERFØRT': [
            try_improve_incoming_transaction
        ],
        'StraksOvf': [
            try_improve_from_vipps
        ],
        'VARER': [
            try_improve_date,
            try_improve_from_purchase
        ],
        'VISA VARE': [
            try_improve_date,
            try_improve_from_purchase
        ],
        'AVTGI': [],
        'E-FAKTURA': [],
        'NETTGIRO': []
    }
    yield from getlines_shared(path, column_patterns, processors, ObosArchiveLine)
