from __future__ import annotations
from enum import StrEnum


class SalesOrderState(StrEnum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"


ALLOWED = {
    SalesOrderState.DRAFT: {SalesOrderState.CONFIRMED, SalesOrderState.CANCELLED},
    SalesOrderState.CONFIRMED: {SalesOrderState.FULFILLED, SalesOrderState.CANCELLED},
    SalesOrderState.FULFILLED: set(),
    SalesOrderState.CANCELLED: set(),
}


def transition(current: SalesOrderState, target: SalesOrderState) -> SalesOrderState:
    if target not in ALLOWED[current]:
        raise ValueError(f"invalid sales order transition {current}->{target}")
    return target
