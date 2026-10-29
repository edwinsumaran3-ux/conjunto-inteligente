from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.idempotency import reserve, complete, fingerprint
from backend.app.modules.clinical.domain.clinical import Patient, Encounter, EncounterState, Diagnosis, MedicationOrder, transition
from backend.app.modules.clinical.schemas.clinical import CreatePatientInput, CreateEncounterInput, ClinicalUpdateInput
class ClinicalService:
    async def create_patient(self,s:AsyncSession,t:UUID,u:UUID,c:CreatePatientInput)->UUID:
        p=Patient(t,c.document_type,c.document_number,c.given_name,c.family_name,c.birth_date,c.sex_at_birth); p.validate()
        route='POST:/clinical/patients'; idem=await reserve(s,t,c.idempotency_key,route,fingerprint(c.model_dump(mode='json')))
        if idem.status=='completed': return UUID(str(idem.response_body['id']))
        if idem.status=='in_progress': raise RuntimeError('request with this idempotency key is already in progress')
        row=await s.scalar(text("""INSERT INTO clinical_patients(tenant_id,document_type,document_number,given_name,family_name,birth_date,sex_at_birth,created_by) VALUES(:t,:dt,:dn,:g,:f,:b,:sex,:u) ON CONFLICT(tenant_id,document_type,document_number) DO UPDATE SET given_name=EXCLUDED.given_name,family_name=EXCLUDED.family_name RETURNING id"""),{'t':t,'dt':c.document_type,'dn':c.document_number,'g':c.given_name,'f':c.family_name,'b':c.birth_date,'sex':c.sex_at_birth,'u':u})
        pid=UUID(str(row)); await complete(s,t,c.idempotency_key,route,201,{'id':str(pid)}); return pid
    async def create_encounter(self,s:AsyncSession,t:UUID,u:UUID,c:CreateEncounterInput)->UUID:
        e=Encounter(c.patient_id,c.practitioner_id,c.encounter_type,EncounterState.OPEN,datetime.now(timezone.utc)); e.validate()
        route='POST:/clinical/encounters'; idem=await reserve(s,t,c.idempotency_key,route,fingerprint(c.model_dump(mode='json')))
        if idem.status=='completed': return UUID(str(idem.response_body['id']))
        if idem.status=='in_progress': raise RuntimeError('request with this idempotency key is already in progress')
        pid=await s.scalar(text('SELECT id FROM clinical_patients WHERE tenant_id=:t AND id=:p'),{'t':t,'p':c.patient_id})
        if pid is None: raise ValueError('patient not found in tenant')
        eid=UUID(str(await s.scalar(text("""INSERT INTO clinical_encounters(tenant_id,patient_id,practitioner_id,encounter_type,state,started_at,created_by) VALUES(:t,:p,:pr,:ty,'OPEN',:st,:u) RETURNING id"""),{'t':t,'p':c.patient_id,'pr':c.practitioner_id,'ty':c.encounter_type,'st':e.started_at,'u':u})))
        await complete(s,t,c.idempotency_key,route,201,{'id':str(eid)}); return eid
    async def transition_encounter(self,s:AsyncSession,t:UUID,u:UUID,eid:UUID,target:EncounterState)->None:
        row=(await s.execute(text('SELECT state FROM clinical_encounters WHERE tenant_id=:t AND id=:e FOR UPDATE'),{'t':t,'e':eid})).mappings().one_or_none()
        if row is None: raise ValueError('encounter not found')
        current=EncounterState(row['state']); new=transition(current,target)
        await s.execute(text('UPDATE clinical_encounters SET state=:new,completed_at=CASE WHEN :new=\'COMPLETED\' THEN now() ELSE completed_at END,updated_by=:u WHERE tenant_id=:t AND id=:e AND state=:old'),{'new':new.value,'u':u,'t':t,'e':eid,'old':current.value})
    async def add_update(self,s:AsyncSession,t:UUID,u:UUID,eid:UUID,c:ClinicalUpdateInput)->None:
        exists=await s.scalar(text('SELECT id FROM clinical_encounters WHERE tenant_id=:t AND id=:e AND state=\'IN_PROGRESS\''),{'t':t,'e':eid})
        if exists is None: raise ValueError('encounter must be IN_PROGRESS')
        if c.diagnosis:
            d=Diagnosis(c.diagnosis.code,c.diagnosis.description,c.diagnosis.primary); d.validate()
            await s.execute(text('INSERT INTO clinical_diagnoses(tenant_id,encounter_id,code,description,is_primary,created_by) VALUES(:t,:e,:c,:d,:p,:u)'),{'t':t,'e':eid,'c':d.code,'d':d.description,'p':d.primary,'u':u})
        if c.medication:
            m=MedicationOrder(c.medication.medication_code,c.medication.medication_name,c.medication.dose,c.medication.dose_unit,c.medication.route,c.medication.frequency,c.medication.start_date,c.medication.end_date); m.validate()
            await s.execute(text('INSERT INTO clinical_medication_orders(tenant_id,encounter_id,medication_code,medication_name,dose,dose_unit,route,frequency,start_date,end_date,created_by) VALUES(:t,:e,:c,:n,:dose,:unit,:r,:freq,:sd,:ed,:u)'),{'t':t,'e':eid,'c':m.medication_code,'n':m.medication_name,'dose':m.dose,'unit':m.dose_unit,'r':m.route.value,'freq':m.frequency,'sd':m.start_date,'ed':m.end_date,'u':u})
        if c.clinical_note is not None:
            if not c.clinical_note.strip(): raise ValueError('clinical note cannot be blank')
            await s.execute(text('INSERT INTO clinical_notes(tenant_id,encounter_id,note_text,created_by) VALUES(:t,:e,:n,:u)'),{'t':t,'e':eid,'n':c.clinical_note,'u':u})
