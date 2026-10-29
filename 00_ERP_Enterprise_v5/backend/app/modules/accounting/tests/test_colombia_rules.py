from decimal import Decimal
import pytest
from backend.app.modules.accounting.domain.colombia import ElectronicIdentity, ElectronicDocumentKind
from backend.app.modules.billing.domain.invoice_lifecycle import InvoiceState, transition
from backend.app.modules.finance.domain.payment_allocation import Allocation, allocate

def test_invoice_requires_cufe():
    with pytest.raises(ValueError):
        ElectronicIdentity(ElectronicDocumentKind.INVOICE).validate()

def test_note_requires_cude():
    with pytest.raises(ValueError):
        ElectronicIdentity(ElectronicDocumentKind.CREDIT_NOTE).validate()

def test_lifecycle_cannot_skip_submission():
    assert transition(InvoiceState.READY,InvoiceState.SUBMITTING) is InvoiceState.SUBMITTING
    with pytest.raises(ValueError): transition(InvoiceState.READY,InvoiceState.VALIDATED)

def test_payment_allocation_cannot_overallocate():
    with pytest.raises(ValueError):
        allocate(Decimal('100'),[Allocation('a',Decimal('101'))],{'a':Decimal('100')})
