from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal,InvalidOperation
from enum import StrEnum
class AccountKind(StrEnum): ASSET='ASSET'; LIABILITY='LIABILITY'; EQUITY='EQUITY'; REVENUE='REVENUE'; EXPENSE='EXPENSE'
@dataclass(frozen=True,slots=True)
class Money:
    amount:Decimal; currency:str
    def __post_init__(self):
        if self.amount<0: raise ValueError('money amount cannot be negative')
        if len(self.currency)!=3 or not self.currency.isalpha(): raise ValueError('currency must be ISO-like 3 letters')
        object.__setattr__(self,'currency',self.currency.upper())
def decimal(value:str|int|Decimal)->Decimal:
    try:return Decimal(str(value))
    except InvalidOperation as exc:raise ValueError('invalid decimal') from exc
