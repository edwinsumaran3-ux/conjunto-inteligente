"""Pure domain rules for sales orders. No I/O, no framework imports."""
from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

@dataclass(frozen=True, slots=True)
class SalesOrderLine:
    item_id: UUID
    quantity: Decimal
    unit_price: Decimal
    billing_account_id: UUID | None = None
    taxes: tuple[tuple[str, Decimal], ...] = ()
    def validate(self) -> None:
        if self.quantity <= 0: raise ValueError("sales order line quantity must be strictly positive")
        if self.unit_price < 0: raise ValueError("sales order line unit_price cannot be negative")
        for code, rate in self.taxes:
            if not code or rate < 0: raise ValueError("invalid sales order tax")
    def subtotal(self) -> Decimal: return self.quantity * self.unit_price

@dataclass(frozen=True, slots=True)
class SalesOrder:
    tenant_id: UUID
    partner_id: UUID
    currency: str
    invoice_series: str = ""
    payment_terms_days: int = 0
    lines: tuple[SalesOrderLine, ...] = field(default_factory=tuple)
    id: UUID | None = None
    def validate(self) -> None:
        if not self.lines: raise ValueError("sales order must have at least one line")
        if len(self.currency) != 3: raise ValueError("sales order currency must be a 3-letter ISO code")
        if self.payment_terms_days < 0: raise ValueError("payment terms cannot be negative")
        for line in self.lines: line.validate()
    def total(self) -> Decimal: return sum((line.subtotal() for line in self.lines), Decimal("0"))
