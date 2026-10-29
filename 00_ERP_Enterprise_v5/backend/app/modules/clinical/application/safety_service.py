from __future__ import annotations
from datetime import date, timezone, datetime
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.modules.clinical.schemas.safety import *

class ClinicalSafetyService:
    async def _patient(self,s,t,p):
        if await s.scalar(text('SELECT id FROM clinical_patients WHERE tenant_id=:t AND id=:p'),{'t':t,'p':p}) is None: raise ValueError('patient not found in tenant')
    async def _encounter(self,s,t,e, require_active=True):
        row=(await s.execute(text('SELECT patient_id,state FROM clinical_encounters WHERE tenant_id=:t AND id=:e FOR UPDATE'),{'t':t,'e':e})).mappings().one_or_none()
        if not row: raise ValueError('encounter not found')
        if require_active and row['state']!='IN_PROGRESS': raise ValueError('encounter must be IN_PROGRESS')
        return UUID(str(row['patient_id']))
    async def add_allergy(self,s,t,u,c:AllergyInput):
        await self._patient(s,t,c.patient_id)
        # Deliberately no UPDATE/DELETE: corrections are new facts; existing active allergy creates a safety event.
        aid=await s.scalar(text('INSERT INTO clinical_allergies(tenant_id,patient_id,substance_code,substance_name,reaction,severity,recorded_by) VALUES(:t,:p,:c,:n,:r,:s,:u) RETURNING id'),{'t':t,'p':c.patient_id,'c':c.substance_code,'n':c.substance_name,'r':c.reaction,'s':c.severity,'u':u})
        return UUID(str(aid))
    async def add_vitals(self,s,t,u,c:VitalInput):
        await self._encounter(s,t,c.encounter_id)
        vals=c.model_dump(); vals.update(t=t,u=u)
        vid=await s.scalar(text('INSERT INTO clinical_vitals(tenant_id,encounter_id,measured_at,systolic_bp,diastolic_bp,heart_rate,respiratory_rate,temperature_c,oxygen_saturation,weight_kg,height_cm,recorded_by) VALUES(:t,:encounter_id,:measured_at,:systolic_bp,:diastolic_bp,:heart_rate,:respiratory_rate,:temperature_c,:oxygen_saturation,:weight_kg,:height_cm,:u) RETURNING id'),vals)
        return UUID(str(vid))
    async def order_lab(self,s,t,u,c:LabOrderInput):
        await self._encounter(s,t,c.encounter_id)
        row=await s.scalar(text('INSERT INTO clinical_lab_orders(tenant_id,encounter_id,test_code,test_name,priority,clinical_question,ordered_by) VALUES(:t,:e,:c,:n,:p,:q,:u) RETURNING id'),{'t':t,'e':c.encounter_id,'c':c.test_code,'n':c.test_name,'p':c.priority,'q':c.clinical_question,'u':u}); return UUID(str(row))
    async def result_lab(self,s,t,u,lid,c:LabResultInput):
        row=(await s.execute(text('SELECT id FROM clinical_lab_orders WHERE tenant_id=:t AND id=:i FOR UPDATE'),{'t':t,'i':lid})).scalar_one_or_none()
        if row is None: raise ValueError('lab order not found')
        await s.execute(text("UPDATE clinical_lab_orders SET status=:status,result_text=:r,result_at=now(),result_by=:u WHERE tenant_id=:t AND id=:i AND status IN ('ORDERED','COLLECTED')"),{'status':c.status,'r':c.result_text,'u':u,'t':t,'i':lid})
    async def order_imaging(self,s,t,u,c:ImagingOrderInput):
        await self._encounter(s,t,c.encounter_id)
        row=await s.scalar(text('INSERT INTO clinical_imaging_orders(tenant_id,encounter_id,modality,study_code,study_name,priority,indication,ordered_by) VALUES(:t,:e,:m,:c,:n,:p,:i,:u) RETURNING id'),{'t':t,'e':c.encounter_id,'m':c.modality,'c':c.study_code,'n':c.study_name,'p':c.priority,'i':c.indication,'u':u}); return UUID(str(row))
    async def report_imaging(self,s,t,u,iid,c:ImagingReportInput):
        row=(await s.execute(text('SELECT id FROM clinical_imaging_orders WHERE tenant_id=:t AND id=:i FOR UPDATE'),{'t':t,'i':iid})).scalar_one_or_none()
        if row is None: raise ValueError('imaging order not found')
        await s.execute(text("UPDATE clinical_imaging_orders SET status=:status,report_text=:r,reported_at=now(),reported_by=:u WHERE tenant_id=:t AND id=:i AND status IN ('ORDERED','PERFORMED')"),{'status':c.status,'r':c.report_text,'u':u,'t':t,'i':iid})
    async def create_care_plan(self,s,t,u,c:CarePlanInput):
        await self._patient(s,t,c.patient_id)
        if c.target_date and c.target_date<c.start_date: raise ValueError('target_date cannot precede start_date')
        if c.encounter_id: await self._encounter(s,t,c.encounter_id,False)
        row=await s.scalar(text('INSERT INTO clinical_care_plans(tenant_id,patient_id,encounter_id,title,goals,interventions,start_date,target_date,created_by) VALUES(:t,:p,:e,:title,:goals,:interventions,:sd,:td,:u) RETURNING id'),{'t':t,'p':c.patient_id,'e':c.encounter_id,'title':c.title,'goals':c.goals,'interventions':c.interventions,'sd':c.start_date,'td':c.target_date,'u':u}); return UUID(str(row))
    async def medication_safety(self,s,t,patient_id,medication_code):
        await self._patient(s,t,patient_id)
        allergies=(await s.execute(text("SELECT substance_code,substance_name,severity FROM clinical_allergies WHERE tenant_id=:t AND patient_id=:p AND status='ACTIVE'"),{'t':t,'p':patient_id})).mappings().all()
        hits=[dict(x) for x in allergies if x['substance_code'].casefold()==medication_code.casefold() or x['substance_name'].casefold()==medication_code.casefold()]
        active=(await s.execute(text("SELECT medication_code,medication_name FROM clinical_medication_orders m JOIN clinical_encounters e ON e.tenant_id=m.tenant_id AND e.id=m.encounter_id WHERE m.tenant_id=:t AND e.patient_id=:p AND m.end_date IS NULL"),{'t':t,'p':patient_id})).mappings().all()
        dup=[dict(x) for x in active if x['medication_code'].casefold()==medication_code.casefold()]
        return {'allergy_conflicts':hits,'duplicate_active_medications':dup,'safe_to_proceed':not hits and not dup}
