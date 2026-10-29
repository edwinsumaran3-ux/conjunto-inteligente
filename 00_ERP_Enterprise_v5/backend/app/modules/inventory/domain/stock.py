"""Pure inventory stock rules. No I/O or framework dependencies."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

class StockDirection(StrEnum):
    IN = "IN"
    OUT = "OUT"

@dataclass(frozen=True, slots=True)
class StockMovement:
    direction: StockDirection
    quantity: Decimal

    def validate(self) -> None:
        if self.quantity <= 0:
            raise ValueError("stock movement quantity must be strictly positive")

    def resulting_balance(self, current: Decimal) -> Decimal:
        self.validate()
        if self.direction is StockDirection.IN:
            return current + self.quantity
        next_balance = current - self.quantity
        if next_balance < 0:
            raise ValueError("insufficient stock")
        return next_balance
