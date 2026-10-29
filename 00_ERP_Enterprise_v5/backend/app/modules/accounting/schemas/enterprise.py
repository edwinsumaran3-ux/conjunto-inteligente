from datetime import date
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel,Field,field_validator

class InvoiceTaxIn(BaseModel):
    tax_code:str=Field(min_length=1,max_length=30)
    rate:Decimal=Field(ge=0,max_digits=12,decimal_places=6)

class InvoiceLineIn(BaseModel):
    description:str=Field(min_length=1,max_length=500)
    quantity:Decimal=Field(gt=0,max_digits=20,decimal_places=6)
    unit_price:Decimal=Field(ge=0,max_digits=20,decimal_places=6)
    account_id:UUID
    taxes:list[InvoiceTaxIn]=Field(default_factory=list)

class SalesInvoiceIn(BaseModel):
    customer_id:UUID
    issue_date:date
    due_date:date
    currency:str=Field(min_length=3,max_length=3)
    lines:list[InvoiceLineIn]=Field(min_length=1,max_length=500)
    idempotency_key:str=Field(min_length=16,max_length=255)
    @field_validator('currency')
    @classmethod
    def currency_upper(cls,v): return v.upper()
