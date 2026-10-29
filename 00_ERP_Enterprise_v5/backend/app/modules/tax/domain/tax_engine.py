from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

CENT=Decimal('0.01')
@dataclass(frozen=True, slots=True)
class TaxLine:
    base: Decimal
    rate: Decimal
    tax_code: str
    def amount(self)->Decimal:
        if self.base < 0 or self.rate < 0: raise ValueError('tax base/rate cannot be negative')
        return (self.base*self.rate/Decimal('100')).quantize(CENT,ROUND_HALF_UP)

def calculate(lines:list[TaxLine])->dict[str,Decimal]:
    result:dict[str,Decimal]={}
    for line in lines:
        result[line.tax_code]=result.get(line.tax_code,Decimal('0'))+line.amount()
    return result
