from pydantic import BaseModel, Field
from uuid import UUID
from decimal import Decimal

class CreateInventoryItemInput(BaseModel):
    sku: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=255)
    unit: str = Field(min_length=1, max_length=20)

class RegisterStockMovementInput(BaseModel):
    item_id: UUID
    direction: str
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=6)
    reason: str = Field(min_length=1, max_length=500)
    reference: str | None = Field(default=None, max_length=255)
    idempotency_key: str = Field(min_length=8, max_length=255)
