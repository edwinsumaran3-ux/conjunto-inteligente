from uuid import UUID
from fastapi import APIRouter, Depends
from backend.app.api.deps import AuthContext,get_auth_context,get_tenant_session
from backend.app.modules.clinical.application.clinical_service import ClinicalService
from backend.app.modules.clinical.schemas.clinical import CreatePatientInput,CreateEncounterInput,ClinicalUpdateInput
from backend.app.modules.clinical.domain.clinical import EncounterState
router=APIRouter(prefix='/clinical',tags=['clinical']); service=ClinicalService()
@router.post('/patients',status_code=201)
async def create_patient(cmd:CreatePatientInput,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    return {'id':str(await service.create_patient(session,UUID(auth.tenant_id),UUID(auth.user_id),cmd)),'status':'ACTIVE'}
@router.post('/encounters',status_code=201)
async def create_encounter(cmd:CreateEncounterInput,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    return {'id':str(await service.create_encounter(session,UUID(auth.tenant_id),UUID(auth.user_id),cmd)),'status':'OPEN'}
@router.post('/encounters/{encounter_id}/start',status_code=204)
async def start(encounter_id:UUID,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)): await service.transition_encounter(session,UUID(auth.tenant_id),UUID(auth.user_id),encounter_id,EncounterState.IN_PROGRESS)
@router.post('/encounters/{encounter_id}/update',status_code=204)
async def update(encounter_id:UUID,cmd:ClinicalUpdateInput,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)): await service.add_update(session,UUID(auth.tenant_id),UUID(auth.user_id),encounter_id,cmd)
@router.post('/encounters/{encounter_id}/complete',status_code=204)
async def complete(encounter_id:UUID,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    await service.transition_encounter(session,UUID(auth.tenant_id),UUID(auth.user_id),encounter_id,EncounterState.COMPLETED)
    from backend.app.platform.realtime.service import publish   # solo identificadores: nunca datos clínicos en el bus
    await publish(session,tenant_id=UUID(auth.tenant_id),topic='clinical.encounter.completed',payload={'encounter_id':str(encounter_id)},correlation_id=str(encounter_id))
@router.post('/encounters/{encounter_id}/cancel',status_code=204)
async def cancel(encounter_id:UUID,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)): await service.transition_encounter(session,UUID(auth.tenant_id),UUID(auth.user_id),encounter_id,EncounterState.CANCELLED)

from backend.app.modules.clinical.schemas.safety import AllergyInput, VitalInput, LabOrderInput, LabResultInput, ImagingOrderInput, ImagingReportInput, CarePlanInput
from backend.app.modules.clinical.application.safety_service import ClinicalSafetyService
safety_service=ClinicalSafetyService()

@router.post('/patients/{patient_id}/allergies',status_code=201)
async def add_allergy(patient_id:UUID,cmd:AllergyInput,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    if cmd.patient_id != patient_id: raise ValueError('patient_id mismatch')
    return {'id':str(await safety_service.add_allergy(session,UUID(auth.tenant_id),UUID(auth.user_id),cmd))}

@router.post('/encounters/{encounter_id}/vitals',status_code=201)
async def add_vitals(encounter_id:UUID,cmd:VitalInput,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    if cmd.encounter_id != encounter_id: raise ValueError('encounter_id mismatch')
    return {'id':str(await safety_service.add_vitals(session,UUID(auth.tenant_id),UUID(auth.user_id),cmd))}

@router.post('/encounters/{encounter_id}/labs',status_code=201)
async def order_lab(encounter_id:UUID,cmd:LabOrderInput,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    if cmd.encounter_id != encounter_id: raise ValueError('encounter_id mismatch')
    return {'id':str(await safety_service.order_lab(session,UUID(auth.tenant_id),UUID(auth.user_id),cmd)),'status':'ORDERED'}

@router.post('/labs/{lab_id}/result',status_code=204)
async def result_lab(lab_id:UUID,cmd:LabResultInput,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    await safety_service.result_lab(session,UUID(auth.tenant_id),UUID(auth.user_id),lab_id,cmd)

@router.post('/encounters/{encounter_id}/imaging',status_code=201)
async def order_imaging(encounter_id:UUID,cmd:ImagingOrderInput,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    if cmd.encounter_id != encounter_id: raise ValueError('encounter_id mismatch')
    return {'id':str(await safety_service.order_imaging(session,UUID(auth.tenant_id),UUID(auth.user_id),cmd)),'status':'ORDERED'}

@router.post('/imaging/{imaging_id}/report',status_code=204)
async def report_imaging(imaging_id:UUID,cmd:ImagingReportInput,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    await safety_service.report_imaging(session,UUID(auth.tenant_id),UUID(auth.user_id),imaging_id,cmd)

@router.post('/patients/{patient_id}/care-plans',status_code=201)
async def create_care_plan(patient_id:UUID,cmd:CarePlanInput,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    if cmd.patient_id != patient_id: raise ValueError('patient_id mismatch')
    return {'id':str(await safety_service.create_care_plan(session,UUID(auth.tenant_id),UUID(auth.user_id),cmd)),'status':'ACTIVE'}

@router.get('/patients/{patient_id}/medication-safety')
async def medication_safety(patient_id:UUID,medication_code:str,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    return await safety_service.medication_safety(session,UUID(auth.tenant_id),patient_id,medication_code)
