"""Datos maestros de SST (reglas, evidencias con doble control, ATS con firmas, activos, matriz de autoridad, permisos).
El motor de reglas los LEÍA pero ninguna API permitía crearlos."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from backend.app.api.deps import AuthContext, get_auth_context, get_tenant_session

router = APIRouter(prefix="/sst/master", tags=["sst-master"])
SST_ADMIN = {"admin", "administrator", "sst_admin", "sst_manager"}
def _gate(a: AuthContext, roles=SST_ADMIN):
    if not (roles & set(a.roles)): raise HTTPException(403, {"code": "SST_ROLE_REQUIRED"})
js = lambda v: json.dumps(v, ensure_ascii=False, default=str)

class RuleIn(BaseModel):
    jurisdiction: str = Field(min_length=1, max_length=40); activity_type: str = Field(min_length=1, max_length=120); rule_key: str = Field(min_length=1, max_length=120)
    definition: dict; effective_from: datetime | None = None; expires_at: datetime | None = None
class EvidenceIn(BaseModel):
    evidence_type: str = Field(min_length=1, max_length=120); scope_kind: str | None = None; scope_id: UUID | None = None
    issued_at: datetime | None = None; expires_at: datetime | None = None; file_ref: str | None = None
class ReviewIn(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$"); note: str | None = None
class AtsIn(BaseModel):
    title: str = Field(min_length=1, max_length=200); steps: list[dict] = Field(min_length=1); required_signers: list[UUID] = Field(min_length=1)
class AssetIn(BaseModel):
    asset_type: str = Field(min_length=1, max_length=80); zone_id: UUID | None = None; capacity_units: float | None = Field(default=None, ge=0)
    inspection_valid_until: datetime | None = None; expires_at: datetime | None = None
class MatrixIn(BaseModel):
    rules: list[dict] = Field(min_length=1)
class PermitIn(BaseModel):
    activity_id: UUID; ats_id: UUID; permit_type: str = Field(min_length=1, max_length=80); zone_id: UUID; contractor_id: UUID | None = None
    worker_ids: list[str] = Field(default_factory=list, max_length=500); valid_from: datetime; valid_to: datetime; approval_id: UUID | None = None

@router.post("/rules", status_code=201)
async def create_rule(r: RuleIn, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    _gate(a); t = UUID(a.tenant_id)
    if not isinstance(r.definition.get("requirements"), list): raise ValueError("definition.requirements debe ser una lista")
    v = (await s.execute(text("SELECT COALESCE(max(version),0)+1 FROM sst_rules WHERE tenant_id=:t AND jurisdiction=:j AND activity_type=:a AND rule_key=:k"), {"t": t, "j": r.jurisdiction, "a": r.activity_type, "k": r.rule_key})).scalar_one()
    i = (await s.execute(text("""INSERT INTO sst_rules(tenant_id,jurisdiction,activity_type,rule_key,version,definition,effective_from,expires_at,approved_by)
        VALUES(:t,:j,:a,:k,:v,CAST(:d AS jsonb),COALESCE(:ef,now()),:ex,:u) RETURNING id"""), {"t": t, "j": r.jurisdiction, "a": r.activity_type, "k": r.rule_key, "v": v, "d": js(r.definition), "ef": r.effective_from, "ex": r.expires_at, "u": UUID(a.user_id)})).scalar_one()
    return {"id": str(i), "version": v}

@router.post("/evidence", status_code=201)
async def upload_evidence(r: EvidenceIn, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    t = UUID(a.tenant_id)
    i = (await s.execute(text("""INSERT INTO sst_evidence(tenant_id,evidence_type,scope_kind,scope_id,status,issued_at,expires_at,uploaded_by,file_ref)
        VALUES(:t,:e,:k,:sid,'pending_review',:ia,:ex,:u,:f) RETURNING id"""), {"t": t, "e": r.evidence_type, "k": r.scope_kind, "sid": r.scope_id, "ia": r.issued_at, "ex": r.expires_at, "u": UUID(a.user_id), "f": r.file_ref})).scalar_one()
    return {"id": str(i), "status": "pending_review"}

@router.post("/evidence/{evidence_id}/review")
async def review_evidence(evidence_id: UUID, r: ReviewIn, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    """Doble control: quien sube la evidencia NO puede revisarla."""
    _gate(a, SST_ADMIN | {"sst_reviewer"}); t = UUID(a.tenant_id)
    row = (await s.execute(text("SELECT uploaded_by,status FROM sst_evidence WHERE tenant_id=:t AND id=:i FOR UPDATE"), {"t": t, "i": evidence_id})).mappings().first()
    if not row: raise HTTPException(404, "evidence not found")
    if row["status"] != "pending_review": raise HTTPException(409, {"code": "EVIDENCE_NOT_PENDING"})
    if str(row["uploaded_by"]) == a.user_id: raise HTTPException(409, {"code": "SELF_REVIEW_FORBIDDEN"})
    st = "valid" if r.decision == "approve" else "rejected"
    await s.execute(text("UPDATE sst_evidence SET status=:st,reviewed_by=:u,reviewed_at=now(),review_note=:n WHERE id=:i"), {"st": st, "u": UUID(a.user_id), "n": r.note, "i": evidence_id})
    return {"id": str(evidence_id), "status": st}

@router.post("/ats", status_code=201)
async def create_ats(r: AtsIn, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    _gate(a, SST_ADMIN | {"sst_supervisor"})
    i = (await s.execute(text("INSERT INTO sst_ats(tenant_id,title,steps,required_signers) VALUES(:t,:ti,CAST(:st AS jsonb),CAST(:rs AS jsonb)) RETURNING id"),
                         {"t": UUID(a.tenant_id), "ti": r.title, "st": js(r.steps), "rs": js([str(x) for x in r.required_signers])})).scalar_one()
    return {"id": str(i)}

@router.post("/ats/{ats_id}/sign", status_code=200)
async def sign_ats(ats_id: UUID, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    row = (await s.execute(text("SELECT required_signers,signatures FROM sst_ats WHERE tenant_id=:t AND id=:i FOR UPDATE"), {"t": UUID(a.tenant_id), "i": ats_id})).mappings().first()
    if not row: raise HTTPException(404, "ats not found")
    if a.user_id not in [str(x) for x in row["required_signers"]]: raise HTTPException(403, {"code": "NOT_A_REQUIRED_SIGNER"})
    sigs = [x for x in row["signatures"] if x.get("user_id") != a.user_id] + [{"user_id": a.user_id, "signed_at": datetime.now(timezone.utc).isoformat()}]
    await s.execute(text("UPDATE sst_ats SET signatures=CAST(:g AS jsonb) WHERE id=:i"), {"g": js(sigs), "i": ats_id})
    return {"signed": len(sigs), "required": len(row["required_signers"])}

@router.post("/assets", status_code=201)
async def register_asset(r: AssetIn, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    _gate(a, SST_ADMIN | {"sst_supervisor"})
    i = (await s.execute(text("INSERT INTO sst_asset_registry(tenant_id,asset_type,zone_id,capacity_units,inspection_valid_until,expires_at) VALUES(:t,:y,:z,:c,:iv,:ex) RETURNING id"),
                         {"t": UUID(a.tenant_id), "y": r.asset_type, "z": r.zone_id, "c": r.capacity_units, "iv": r.inspection_valid_until, "ex": r.expires_at})).scalar_one()
    return {"id": str(i)}

@router.put("/authority-matrix", status_code=201)
async def set_matrix(r: MatrixIn, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    _gate(a); t = UUID(a.tenant_id)
    for rule in r.rules:
        if not {"request_type", "risk_levels", "approver_role"} <= set(rule): raise ValueError("cada regla requiere request_type, risk_levels y approver_role")
    v = (await s.execute(text("SELECT COALESCE(max(version),0)+1 FROM sst_authority_matrix WHERE tenant_id=:t"), {"t": t})).scalar_one()
    await s.execute(text("INSERT INTO sst_authority_matrix(tenant_id,version,matrix,approved_by) VALUES(:t,:v,CAST(:m AS jsonb),:u)"), {"t": t, "v": v, "m": js({"rules": r.rules}), "u": UUID(a.user_id)})
    return {"version": v}

@router.post("/work-permits", status_code=201)
async def create_permit(r: PermitIn, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    _gate(a, SST_ADMIN | {"sst_supervisor"}); t = UUID(a.tenant_id)
    if r.valid_to <= r.valid_from: raise ValueError("valid_to debe ser posterior a valid_from")
    ats = (await s.execute(text("SELECT version FROM sst_ats WHERE tenant_id=:t AND id=:i"), {"t": t, "i": r.ats_id})).scalar_one_or_none()
    if ats is None: raise HTTPException(404, "ats not found")
    i = (await s.execute(text("""INSERT INTO sst_work_permits(tenant_id,activity_id,ats_id,ats_version,permit_type,zone_id,contractor_id,worker_ids,valid_from,valid_to,approval_id,status)
        VALUES(:t,:a,:ats,:v,:p,:z,:c,CAST(:w AS jsonb),:vf,:vt,:ap,'draft') RETURNING id"""), {"t": t, "a": r.activity_id, "ats": r.ats_id, "v": ats, "p": r.permit_type, "z": r.zone_id, "c": r.contractor_id, "w": js(r.worker_ids), "vf": r.valid_from, "vt": r.valid_to, "ap": r.approval_id})).scalar_one()
    return {"id": str(i), "status": "draft"}


class ExceptionIn(BaseModel):
    activity_id: UUID; requirement_key: str = Field(min_length=1, max_length=120); approval_id: UUID; expires_at: datetime

@router.post("/exceptions", status_code=201)
async def create_exception(r: ExceptionIn, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    """Una excepción a un requisito SOLO existe respaldada por una aprobación humana vigente, y siempre vence."""
    _gate(a, SST_ADMIN | {"sst_supervisor"}); t = UUID(a.tenant_id)
    if r.expires_at <= datetime.now(timezone.utc): raise ValueError("la excepción debe vencer en el futuro")
    ap = (await s.execute(text("SELECT status,approved_by FROM (SELECT status,decided_by AS approved_by FROM sst_approvals WHERE tenant_id=:t AND id=:i) x"), {"t": t, "i": r.approval_id})).mappings().first()
    if not ap: raise HTTPException(404, "approval not found")
    if ap["status"] != "approved": raise HTTPException(409, {"code": "APPROVAL_NOT_APPROVED"})
    i = (await s.execute(text("INSERT INTO sst_exceptions(tenant_id,activity_id,requirement_key,approval_id,approved_by,expires_at) VALUES(:t,:a,:k,:ap,:u,:ex) RETURNING id"),
                         {"t": t, "a": r.activity_id, "k": r.requirement_key, "ap": r.approval_id, "u": ap["approved_by"], "ex": r.expires_at})).scalar_one()
    return {"id": str(i)}
