from __future__ import annotations
from decimal import Decimal
from dataclasses import dataclass

@dataclass(frozen=True)
class StraightLineDepreciation:
    acquisition_cost: Decimal
    residual_value: Decimal
    useful_life_months: int

    def monthly_amount(self) -> Decimal:
        if self.useful_life_months <= 0:
            raise ValueError("useful_life_months must be positive")
        depreciable = self.acquisition_cost - self.residual_value
        if depreciable < 0:
            raise ValueError("residual value cannot exceed acquisition cost")
        return (depreciable / Decimal(self.useful_life_months)).quantize(Decimal("0.000001"))
