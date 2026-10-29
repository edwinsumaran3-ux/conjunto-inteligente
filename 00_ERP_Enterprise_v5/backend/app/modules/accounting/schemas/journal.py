from datetime import date
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel,Field,field_validator
class JournalLineIn(BaseModel):
    account_id:UUID; debit:Decimal=Field(default=Decimal('0'),ge=0,max_digits=20,decimal_places=6); credit:Decimal=Field(default=Decimal('0'),ge=0,max_digits=20,decimal_places=6); currency:str=Field(min_length=3,max_length=3); description:str|None=Field(default=None,max_length=500); exchange_rate:Decimal=Field(default=Decimal('1'),gt=0,max_digits=20,decimal_places=10)
    @field_validator('currency')
    @classmethod
    def currency_upper(cls,v):return v.upper()
class JournalIn(BaseModel):
    period_id:UUID; entry_date:date; description:str=Field(min_length=1,max_length=500); source_type:str=Field(min_length=1,max_length=60); source_id:UUID|None=None; lines:list[JournalLineIn]=Field(min_length=2,max_length=200)
