from decimal import Decimal
import pytest
from backend.app.modules.accounting.domain.depreciation import StraightLineDepreciation
from backend.app.modules.accounting.domain.withholding import WithholdingCalculator


def test_depreciation_caps_to_remaining_depreciable_value():
    calc = StraightLineDepreciation(Decimal("1000"), Decimal("100"), 12)
    assert calc.monthly_amount() == Decimal("75.000000")


def test_depreciation_rejects_zero_life():
    with pytest.raises(ValueError):
        StraightLineDepreciation(Decimal("100"), Decimal("0"), 0).monthly_amount()


def test_withholding_is_decimal_and_rounds_half_up():
    assert WithholdingCalculator.calculate(Decimal("1000.000000"), Decimal("2.5")) == Decimal("25.000000")
