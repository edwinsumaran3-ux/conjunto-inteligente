from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP

class WithholdingCalculator:
    """Deterministic arithmetic only; legal rates must be supplied by a verified ruleset."""
    @staticmethod
    def calculate(base: Decimal, rate: Decimal) -> Decimal:
        if base < 0 or rate < 0:
            raise ValueError("base and rate must be non-negative")
        return (base * rate / Decimal("100")).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
