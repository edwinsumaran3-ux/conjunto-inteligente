from datetime import date
from decimal import Decimal
import pytest
from backend.app.modules.clinical.domain.clinical import MedicationOrder, MedicationRoute

def test_medication_positive_dose():
    m=MedicationOrder('RX','Drug',Decimal('1'),'mg',MedicationRoute.ORAL,'once',date.today()); m.validate()

def test_medication_rejects_negative_dose():
    with pytest.raises(ValueError): MedicationOrder('RX','Drug',Decimal('-1'),'mg',MedicationRoute.ORAL,'once',date.today()).validate()

def test_medication_rejects_backwards_dates():
    with pytest.raises(ValueError): MedicationOrder('RX','Drug',Decimal('1'),'mg',MedicationRoute.ORAL,'once',date(2026,9,12),date(2026,9,11)).validate()
