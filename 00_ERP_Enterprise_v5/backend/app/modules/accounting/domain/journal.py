from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID
@dataclass(frozen=True,slots=True)
class JournalLine:
    account_id:UUID; debit:Decimal; credit:Decimal; currency:str; description:str|None=None; exchange_rate:Decimal=Decimal('1')
    def __post_init__(self):
        if self.debit<0 or self.credit<0: raise ValueError('negative journal amount')
        if (self.debit==0)==(self.credit==0): raise ValueError('exactly one side must be non-zero')
        if self.exchange_rate<=0: raise ValueError('exchange rate must be positive')
@dataclass(frozen=True,slots=True)
class Journal:
    tenant_id:UUID; period_id:UUID; entry_date:object; description:str; source_type:str; source_id:UUID|None; created_by:UUID; lines:tuple[JournalLine,...]
    def validate(self)->None:
        if len(self.lines)<2: raise ValueError('journal requires at least two lines')
        currencies={x.currency.upper() for x in self.lines}
        for currency in currencies:
            d=sum((x.debit for x in self.lines if x.currency.upper()==currency),Decimal('0')); c=sum((x.credit for x in self.lines if x.currency.upper()==currency),Decimal('0'))
            if d!=c: raise ValueError(f'journal is not balanced for currency {currency}')
        if not self.description.strip() or len(self.description)>500: raise ValueError('invalid description')
