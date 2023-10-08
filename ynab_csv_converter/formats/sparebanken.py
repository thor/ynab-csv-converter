import csv
import locale
import re
from collections import namedtuple
from typing import Any
import datetime

from pydantic import BaseModel, Field, field_validator, field_serializer, model_validator, FieldValidationInfo

from ynab_csv_converter.formats.ynab import YnabLine

Sparebanken = namedtuple('Sparebanken', ["date", "payee", "type", "currency_amount", "currency_rate", "currency", "amount", "merchant_area", "merchant_category", "book_date", "value_date"])

amount_pattern = r'^-?\d{1,}(\.\d{3})*(.\d{1,2})?$'
date_pattern = r'^\d{2}\.\d{2}\.\d{4}'
short_date_pattern = r'(?P<date>\d{2}\.\d{2})'
short_date_format = r'%d.%m'
txn_date_descends = False
visa_card_pattern = r'(?P<card>^\*\d{4} )'
visa_start_pattern = fr'{visa_card_pattern} {short_date_pattern}'
visa_cost_pattern = r'(?P<currency>\w{3}) (?P<amount>\d{1,}\.\d{1,2})'
visa_payee_pattern = r'(?P<payee>.*?)( Kurs: (?P<rate>\d*\.\d*)|$)'

class ParseError(Exception):
    def __init__(self, line: int, path: str) -> None:
        msg = f"There was a problem parsing on line {line} in {path}"
        super().__init__(msg)


class Transaction(BaseModel):
    date: datetime.datetime = Field(..., alias='Dato')
    memo: str | None = None
    payee: str = Field(..., validation_alias='Beskrivelse')
    interest_date: datetime.datetime = Field(None, validation_alias='Rentedato', exclude=True)
    inflow: float = Field(0.0, gt=0, validation_alias='Inn')
    outflow: float = Field(0.0, lt=0, validation_alias='Ut')
    to_account: str  = Field(None, max_length=11, validation_alias='Til konto', exclude=True)
    from_account: str = Field(None, max_length=11, validation_alias='Fra konto', exclude=True)
    category: str = ''

    @field_validator('inflow', 'outflow', mode='before')
    @classmethod
    def convert_comma_to_period(cls, v: str, _: FieldValidationInfo) -> str:
        if not isinstance(v, str):
            return v
        
        return v.replace(',', '.')

    @field_validator('outflow', mode='after')
    @classmethod
    def make_outflows_positive(cls, v: float, _: FieldValidationInfo) -> float:
        return -v

    @field_validator('date', 'interest_date', mode='before')
    def convert_date_format(cls, v: str, _: FieldValidationInfo) -> str:
        if not isinstance(v, str):
            return v

        parts = v.split('.')
        if not len(parts) == 3:
            return v
        
        day, month, year = map(str, parts)
        return f"{year}-{month}-{day}T00:00"

    @model_validator(mode='after')
    def check_flow_is_set(self) -> 'Transaction':
        if not self.inflow and not self.outflow:
            raise ValueError('One of inflow or outflow must be specified')
        return self

    @field_serializer('payee', 'memo')
    def empty_strings(self, v: str | None, _) -> str:
        if v is None:
            return ''
        return v

    #@field_serializer('date')
    #def date_to_string(self, v: datetime.datetime, _) -> str:
    #    return v.strftime("%d/%m/%Y")


def getlines(path: str):
    # Load the transactions
    with open(path, 'r', encoding='utf-8-sig') as handle:
        transactions = csv.reader(handle, delimiter=';', quotechar='"',
                                  quoting=csv.QUOTE_ALL)
        locale.setlocale(locale.LC_ALL, 'nb_NO.UTF-8')

        header = next(transactions)

        for row in transactions:
            try:
                # Convert each row a mapping
                row = dict(zip(header, row))
                # Zip and filter away empty values
                filtered_row = dict(list(filter(lambda kv: kv[1], row.items())))
                row = Transaction(**filtered_row)
                serialized = row.model_dump()
                print(serialized)

                yield YnabLine(**serialized)

            except Exception as e:
                raise ParseError(line=transactions.line_num, path=path) from e
