from decimal import Decimal
from uuid import uuid4
import pytest
from backend.app.modules.sales.domain.order import SalesOrder, SalesOrderLine
from backend.app.modules.sales.domain.order_lifecycle import SalesOrderState, transition


def _line(qty="1", price="10"):
    return SalesOrderLine(item_id=uuid4(), quantity=Decimal(qty), unit_price=Decimal(price))


def test_order_requires_at_least_one_line():
    order = SalesOrder(tenant_id=uuid4(), partner_id=uuid4(), currency="COP", lines=())
    with pytest.raises(ValueError):
        order.validate()


def test_order_currency_must_be_three_letters():
    order = SalesOrder(tenant_id=uuid4(), partner_id=uuid4(), currency="CO", lines=(_line(),))
    with pytest.raises(ValueError):
        order.validate()


def test_line_quantity_must_be_positive():
    with pytest.raises(ValueError):
        _line(qty="0").validate()
    with pytest.raises(ValueError):
        _line(qty="-1").validate()


def test_line_unit_price_cannot_be_negative():
    with pytest.raises(ValueError):
        _line(price="-1").validate()


def test_order_total_sums_line_subtotals():
    order = SalesOrder(
        tenant_id=uuid4(), partner_id=uuid4(), currency="COP",
        lines=(_line("2", "10"), _line("3", "5")),
    )
    order.validate()
    assert order.total() == Decimal("35")


def test_lifecycle_draft_can_confirm_or_cancel():
    assert transition(SalesOrderState.DRAFT, SalesOrderState.CONFIRMED) == SalesOrderState.CONFIRMED
    assert transition(SalesOrderState.DRAFT, SalesOrderState.CANCELLED) == SalesOrderState.CANCELLED


def test_lifecycle_cannot_fulfill_a_draft_directly():
    with pytest.raises(ValueError):
        transition(SalesOrderState.DRAFT, SalesOrderState.FULFILLED)


def test_lifecycle_fulfilled_and_cancelled_are_terminal():
    with pytest.raises(ValueError):
        transition(SalesOrderState.FULFILLED, SalesOrderState.CANCELLED)
    with pytest.raises(ValueError):
        transition(SalesOrderState.CANCELLED, SalesOrderState.CONFIRMED)
