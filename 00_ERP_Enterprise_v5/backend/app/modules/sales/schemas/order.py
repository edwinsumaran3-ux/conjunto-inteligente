from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field, field_validator

class TaxInput(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    rate: Decimal = Field(ge=0, max_digits=12, decimal_places=6)

class SalesOrderLineInput(BaseModel):
    item_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=6)
    unit_price: Decimal = Field(ge=0, max_digits=20, decimal_places=6)
    billing_account_id: UUID
    taxes: list[TaxInput] = Field(default_factory=list, max_length=20)

class CreateSalesOrderInput(BaseModel):
    partner_id: UUID
    currency: str = Field(min_length=3, max_length=3)
    invoice_series: str = Field(min_length=1, max_length=20)
    payment_terms_days: int = Field(default=0, ge=0, le=3650)
    lines: list[SalesOrderLineInput] = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(min_length=8, max_length=255)
    @field_validator('currency')
    @classmethod
    def currency_upper(cls, value: str) -> str:
        return value.upper()

class TransitionInput(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
