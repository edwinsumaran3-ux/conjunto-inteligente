from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4
import pytest
from backend.app.modules.clinical.domain.clinical import *
def test_patient_validation():
    p=Patient(uuid4(),'CC','123','Ana','Lopez',date(1990,1,1),'F'); p.validate(date(2026,9,12))
def test_encounter_lifecycle():
    assert transition(EncounterState.OPEN,EncounterState.IN_PROGRESS) is EncounterState.IN_PROGRESS
    assert transition(EncounterState.IN_PROGRESS,EncounterState.COMPLETED) is EncounterState.COMPLETED
    with pytest.raises(ValueError): transition(EncounterState.COMPLETED,EncounterState.OPEN)
def test_medication_rules():
    m=MedicationOrder('RX','Drug',Decimal('5'),'mg',MedicationRoute.ORAL,'q8h',date(2026,9,12),date(2026,9,13)); m.validate()
    with pytest.raises(ValueError): MedicationOrder('RX','Drug',Decimal('5'),'mg',MedicationRoute.ORAL,'q8h',date(2026,9,14),date(2026,9,13)).validate()
def test_diagnosis_rules():
    Diagnosis('J06.9','Acute upper respiratory infection',True).validate()
