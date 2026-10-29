from __future__ import annotations
from enum import StrEnum

class InvoiceState(StrEnum):
    DRAFT='DRAFT'; CALCULATED='CALCULATED'; READY='READY'; SUBMITTING='SUBMITTING'; VALIDATED='VALIDATED'; REJECTED='REJECTED'; VOIDED='VOIDED'; CANCELLED='CANCELLED'

ALLOWED = {
    InvoiceState.DRAFT:{InvoiceState.CALCULATED,InvoiceState.CANCELLED},
    InvoiceState.CALCULATED:{InvoiceState.READY,InvoiceState.DRAFT,InvoiceState.CANCELLED},
    InvoiceState.READY:{InvoiceState.SUBMITTING,InvoiceState.CANCELLED},
    InvoiceState.SUBMITTING:{InvoiceState.VALIDATED,InvoiceState.REJECTED},
    InvoiceState.REJECTED:{InvoiceState.READY,InvoiceState.CANCELLED},
    InvoiceState.VALIDATED:{InvoiceState.VOIDED},
    InvoiceState.VOIDED:set(), InvoiceState.CANCELLED:set(),
}

def transition(current: InvoiceState, target: InvoiceState)->InvoiceState:
    if target not in ALLOWED[current]:
        raise ValueError(f'invalid invoice transition {current}->{target}')
    return target
