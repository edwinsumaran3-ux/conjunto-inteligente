from decimal import Decimal
import pytest
from backend.app.modules.inventory.domain.stock import StockDirection, StockMovement

def test_increases():
    assert StockMovement(StockDirection.IN, Decimal("2")).resulting_balance(Decimal("3")) == Decimal("5")

def test_out_rejects_negative():
    with pytest.raises(ValueError):
        StockMovement(StockDirection.OUT, Decimal("4")).resulting_balance(Decimal("3"))

def test_zero_rejected():
    with pytest.raises(ValueError):
        StockMovement(StockDirection.IN, Decimal("0")).validate()
