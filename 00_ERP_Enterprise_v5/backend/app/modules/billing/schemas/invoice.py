from datetime import date
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field, field_validator

class TaxInput(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    rate: Decimal = Field(ge=0, max_digits=12, decimal_places=6)

class InvoiceLineInput(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=6)
    unit_price: Decimal = Field(ge=0, max_digits=20, decimal_places=6)
    account_id: UUID
    taxes: list[TaxInput] = Field(default_factory=list, max_length=20)

class CreateInvoiceInput(BaseModel):
    partner_id: UUID
    issue_date: date
    due_date: date
    currency: str = Field(min_length=3, max_length=3)
    series: str = Field(min_length=1, max_length=20)
    lines: list[InvoiceLineInput] = Field(min_length=1, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=255)
    source_type: str | None = Field(default=None, max_length=60)
    source_id: UUID | None = None
    @field_validator('currency')
    @classmethod
    def currency_upper(cls, value: str) -> str:
        return value.upper()

class TransitionInput(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
