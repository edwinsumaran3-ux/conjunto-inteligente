"""Validated finance command schemas."""
from datetime import date
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class AllocationIn(BaseModel):
    payment_id: UUID
    receivable_payable_id: UUID
    amount: Decimal = Field(gt=0, max_digits=20, decimal_places=6)


class CreatePaymentIn(BaseModel):
    company_id: UUID | None = None
    partner_id: UUID | None = None
    treasury_account_id: UUID
    direction: str
    payment_date: date
    amount: Decimal = Field(gt=0, max_digits=20, decimal_places=6)
    currency: str = Field(min_length=3, max_length=3)
    idempotency_key: str = Field(min_length=8, max_length=255)
    external_reference: str | None = Field(default=None, max_length=255)

    @field_validator("direction")
    @classmethod
    def valid_direction(cls, value: str) -> str:
        value=value.upper()
        if value not in {"RECEIPT","DISBURSEMENT"}: raise ValueError("direction must be RECEIPT or DISBURSEMENT")
        return value

    @field_validator("currency")
    @classmethod
    def valid_currency(cls, value: str) -> str:
        return value.upper()
