from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum

CENT = Decimal('0.01')

class DocumentIdentity(StrEnum):
    NIT='31'; CC='13'; CE='22'; PASSPORT='41'; FOREIGN='42'; FOREIGN_NIT='50'

class ElectronicDocumentKind(StrEnum):
    INVOICE='INVOICE'; CREDIT_NOTE='CREDIT_NOTE'; DEBIT_NOTE='DEBIT_NOTE'; SUPPORT='SUPPORT'

class DianState(StrEnum):
    NOT_REQUIRED='NOT_REQUIRED'; PENDING='PENDING'; QUEUED='QUEUED'; SENT='SENT'; VALIDATED='VALIDATED'; REJECTED='REJECTED'; BLOCKED='BLOCKED'

@dataclass(frozen=True, slots=True)
class TaxAmounts:
    taxable: Decimal
    exempt: Decimal
    iva: Decimal
    rete_fuente: Decimal
    rete_iva: Decimal
    rete_ica: Decimal
    def total_due(self, gross: Decimal) -> Decimal:
        return (gross + self.iva - self.rete_fuente - self.rete_iva - self.rete_ica).quantize(CENT, ROUND_HALF_UP)

@dataclass(frozen=True, slots=True)
class ElectronicIdentity:
    kind: ElectronicDocumentKind
    cufe: str|None=None
    cude: str|None=None
    cuds: str|None=None
    def validate(self)->None:
        if self.kind is ElectronicDocumentKind.INVOICE and self.cufe is None:
            raise ValueError('invoice requires CUFE after DIAN validation')
        if self.kind in (ElectronicDocumentKind.CREDIT_NOTE, ElectronicDocumentKind.DEBIT_NOTE) and self.cude is None:
            raise ValueError('credit/debit note requires CUDE after DIAN validation')
        if self.kind is ElectronicDocumentKind.SUPPORT and self.cuds is None:
            raise ValueError('support document requires CUDS after DIAN validation')
