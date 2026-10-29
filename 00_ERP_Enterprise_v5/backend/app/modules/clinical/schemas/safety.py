from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field

class AllergyInput(BaseModel):
    patient_id: UUID; substance_code: str=Field(min_length=1,max_length=100); substance_name: str=Field(min_length=1,max_length=200)
    reaction: str=Field(min_length=1,max_length=500); severity: str=Field(pattern='^(MILD|MODERATE|SEVERE|LIFE_THREATENING|UNKNOWN)$')

class VitalInput(BaseModel):
    encounter_id: UUID; measured_at: datetime
    systolic_bp: Decimal|None=None; diastolic_bp: Decimal|None=None; heart_rate: Decimal|None=None; respiratory_rate: Decimal|None=None
    temperature_c: Decimal|None=None; oxygen_saturation: Decimal|None=None; weight_kg: Decimal|None=None; height_cm: Decimal|None=None

class LabOrderInput(BaseModel):
    encounter_id: UUID; test_code: str=Field(min_length=1,max_length=80); test_name: str=Field(min_length=1,max_length=200)
    priority: str=Field(default='ROUTINE',pattern='^(ROUTINE|URGENT|STAT)$'); clinical_question: str|None=None

class LabResultInput(BaseModel):
    result_text: str=Field(min_length=1); status: str=Field(default='RESULTED',pattern='^(RESULTED|CANCELLED)$')

class ImagingOrderInput(BaseModel):
    encounter_id: UUID; modality: str=Field(min_length=1,max_length=40); study_code: str=Field(min_length=1,max_length=80)
    study_name: str=Field(min_length=1,max_length=200); priority: str=Field(default='ROUTINE',pattern='^(ROUTINE|URGENT|STAT)$'); indication: str=Field(min_length=1)

class ImagingReportInput(BaseModel):
    report_text: str=Field(min_length=1); status: str=Field(default='REPORTED',pattern='^(REPORTED|CANCELLED)$')

class CarePlanInput(BaseModel):
    patient_id: UUID; encounter_id: UUID|None=None; title: str=Field(min_length=1,max_length=200); goals: str=Field(min_length=1); interventions: str=Field(min_length=1)
    start_date: date; target_date: date|None=None
