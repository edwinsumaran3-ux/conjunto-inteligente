from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True, slots=True)
class Allocation:
    invoice_id: str
    amount: Decimal

@dataclass(frozen=True, slots=True)
class AllocationResult:
    allocations: tuple[Allocation,...]
    unapplied: Decimal

def allocate(payment: Decimal, allocations: list[Allocation], outstanding: dict[str,Decimal])->AllocationResult:
    if payment <= 0: raise ValueError('payment must be positive')
    total=Decimal('0'); out=[]
    seen=set()
    for item in allocations:
        if item.invoice_id in seen: raise ValueError('duplicate invoice allocation')
        seen.add(item.invoice_id)
        if item.amount <= 0: raise ValueError('allocation must be positive')
        due=outstanding.get(item.invoice_id)
        if due is None: raise ValueError('invoice not found in outstanding set')
        if item.amount > due: raise ValueError('allocation exceeds outstanding balance')
        total += item.amount; out.append(item)
    if total > payment: raise ValueError('allocations exceed payment')
    return AllocationResult(tuple(out), payment-total)
