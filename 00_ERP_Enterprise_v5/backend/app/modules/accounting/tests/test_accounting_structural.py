from decimal import Decimal
import pytest
from backend.app.modules.accounting.domain.depreciation import StraightLineDepreciation
from backend.app.modules.accounting.domain.withholding import WithholdingCalculator

def test_straight_line_depreciation():
    assert StraightLineDepreciation(Decimal('1200'), Decimal('0'), 12).monthly_amount() == Decimal('100.000000')

def test_residual_cannot_exceed_cost():
    with pytest.raises(ValueError):
        StraightLineDepreciation(Decimal('100'), Decimal('101'), 12).monthly_amount()

def test_withholding_is_deterministic():
    assert WithholdingCalculator.calculate(Decimal('1000'), Decimal('2.5')) == Decimal('25.000000')
