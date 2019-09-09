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

from collections import namedtuple

from . import amount_pattern, date_pattern, try_improve_date, try_improve_from_purchase, \
    try_improve_from_vipps, try_improve_incoming_transaction, getlines_shared

txn_date_descends = False


def getlines(path):
    ObosRecentLine = namedtuple('ObosLine', ['date', 'type', 'text', 'amount'])
    column_patterns = {'date': date_pattern,
                       'type': r'^.+$',
                       'text': r'^.+$',
                       'amount': amount_pattern
                       }
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
    yield from getlines_shared(path, column_patterns, processors, ObosRecentLine)
