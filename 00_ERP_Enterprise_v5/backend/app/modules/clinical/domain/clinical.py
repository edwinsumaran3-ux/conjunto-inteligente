"""Pure clinical domain rules. No persistence, network, or framework dependencies."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

class EncounterState(StrEnum):
    OPEN='OPEN'; IN_PROGRESS='IN_PROGRESS'; COMPLETED='COMPLETED'; CANCELLED='CANCELLED'

class MedicationRoute(StrEnum):
    ORAL='ORAL'; IV='IV'; IM='IM'; SC='SC'; TOPICAL='TOPICAL'; INHALATION='INHALATION'; OTHER='OTHER'

@dataclass(frozen=True, slots=True)
class Patient:
    tenant_id: UUID; document_type: str; document_number: str; given_name: str; family_name: str
    birth_date: date; sex_at_birth: str
    def validate(self, today: date | None = None) -> None:
        today=today or date.today()
        if not self.document_type.strip() or not self.document_number.strip(): raise ValueError('patient identity is required')
        if not self.given_name.strip() or not self.family_name.strip(): raise ValueError('patient name is required')
        if self.birth_date > today: raise ValueError('patient birth_date cannot be in the future')
        if self.sex_at_birth not in {'F','M','X','U'}: raise ValueError('invalid sex_at_birth')

@dataclass(frozen=True, slots=True)
class Encounter:
    patient_id: UUID; practitioner_id: UUID; encounter_type: str
    state: EncounterState = EncounterState.OPEN
    started_at: datetime | None = None
    def validate(self) -> None:
        if not self.encounter_type.strip(): raise ValueError('encounter_type is required')
        if self.state is EncounterState.COMPLETED and self.started_at is None: raise ValueError('completed encounter requires started_at')

def transition(current: EncounterState, target: EncounterState) -> EncounterState:
    allowed={
        EncounterState.OPEN:{EncounterState.IN_PROGRESS,EncounterState.CANCELLED},
        EncounterState.IN_PROGRESS:{EncounterState.COMPLETED,EncounterState.CANCELLED},
        EncounterState.COMPLETED:set(), EncounterState.CANCELLED:set(),
    }
    if target not in allowed[current]: raise ValueError(f'invalid encounter transition {current}->{target}')
    return target

@dataclass(frozen=True, slots=True)
class Diagnosis:
    code: str; description: str; primary: bool=False
    def validate(self) -> None:
        if not self.code.strip() or not self.description.strip(): raise ValueError('diagnosis code and description are required')

@dataclass(frozen=True, slots=True)
class MedicationOrder:
    medication_code: str; medication_name: str; dose: Decimal; dose_unit: str
    route: MedicationRoute; frequency: str; start_date: date; end_date: date | None = None
    def validate(self) -> None:
        if not self.medication_code.strip() or not self.medication_name.strip(): raise ValueError('medication identity is required')
        if self.dose <= 0 or not self.dose_unit.strip() or not self.frequency.strip(): raise ValueError('invalid medication dosage')
        if self.end_date and self.end_date < self.start_date: raise ValueError('medication end_date cannot precede start_date')
