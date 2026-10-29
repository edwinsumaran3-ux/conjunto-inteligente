from __future__ import annotations
from datetime import date
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field
from backend.app.modules.clinical.domain.clinical import MedicationRoute
class CreatePatientInput(BaseModel):
    document_type: str=Field(min_length=1,max_length=30); document_number: str=Field(min_length=1,max_length=80)
    given_name: str=Field(min_length=1,max_length=120); family_name: str=Field(min_length=1,max_length=120)
    birth_date: date; sex_at_birth: str=Field(pattern='^(F|M|X|U)$')
    idempotency_key: str=Field(min_length=8,max_length=200)
class CreateEncounterInput(BaseModel):
    patient_id: UUID; practitioner_id: UUID; encounter_type: str=Field(min_length=1,max_length=80); idempotency_key: str=Field(min_length=8,max_length=200)
class DiagnosisInput(BaseModel):
    code: str=Field(min_length=1,max_length=40); description: str=Field(min_length=1,max_length=500); primary: bool=False
class MedicationInput(BaseModel):
    medication_code: str=Field(min_length=1,max_length=80); medication_name: str=Field(min_length=1,max_length=200)
    dose: Decimal=Field(gt=0); dose_unit: str=Field(min_length=1,max_length=30); route: MedicationRoute
    frequency: str=Field(min_length=1,max_length=80); start_date: date; end_date: date|None=None
class ClinicalUpdateInput(BaseModel):
    diagnosis: DiagnosisInput|None=None; medication: MedicationInput|None=None
    clinical_note: str|None=Field(default=None,max_length=10000)
