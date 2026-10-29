"""Datos maestros/configuración que el código LEE pero ninguna API permitía crear (solo SQL manual):
perfiles de contabilización, cuentas de tesorería, reglas de impuestos y numeración de documentos. Solo administradores."""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from backend.app.api.deps import AuthContext, get_auth_context, get_tenant_session

router = APIRouter(prefix="/config", tags=["config-admin"])
ADMIN = {"admin", "administrator", "finance_admin", "accountant"}
def _admin(a: AuthContext):
    if not (ADMIN & set(a.roles)): raise HTTPException(403, {"code": "CONFIG_ROLE_REQUIRED"})

class PostingProfileIn(BaseModel):
    operation: str = Field(min_length=1, max_length=80, pattern=r"^[A-Z0-9_]+$"); currency: str = Field(default="COP", min_length=3, max_length=3)
    company_id: UUID | None = None; debit_account_id: UUID | None = None; credit_account_id: UUID | None = None
    tax_debit_account_id: UUID | None = None; tax_credit_account_id: UUID | None = None; effective_from: date = date(2000, 1, 1)
class TreasuryAccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=160); currency: str = Field(default="COP", min_length=3, max_length=3)
    ledger_account_id: UUID; company_id: UUID | None = None
class TaxRuleIn(BaseModel):
    code: str = Field(min_length=1, max_length=40); rate: Decimal = Field(ge=0, le=100); rounding_scale: int = Field(default=2, ge=0, le=6)
    company_id: UUID | None = None; effective_from: date = date(2000, 1, 1)
class DocumentSequenceIn(BaseModel):
    document_type: str = Field(min_length=1, max_length=40); series: str = Field(min_length=1, max_length=20)
    padding: int = Field(default=8, ge=1, le=16); start: int = Field(default=1, ge=1); company_id: UUID | None = None

@router.post("/posting-profiles", status_code=201)
async def create_profile(r: PostingProfileIn, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    _admin(a); pid = uuid4()
    await s.execute(text("""INSERT INTO accounting_posting_profiles(id,tenant_id,company_id,operation,currency,debit_account_id,credit_account_id,tax_debit_account_id,tax_credit_account_id,effective_from)
        VALUES(:id,:t,:c,:op,:cur,:d,:cr,:td,:tc,:ef)"""), {"id": pid, "t": UUID(a.tenant_id), "c": r.company_id, "op": r.operation, "cur": r.currency, "d": r.debit_account_id,
        "cr": r.credit_account_id, "td": r.tax_debit_account_id, "tc": r.tax_credit_account_id, "ef": r.effective_from})
    return {"id": str(pid)}
@router.get("/posting-profiles")
async def list_profiles(a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    rows = (await s.execute(text("SELECT id,operation,currency,debit_account_id,credit_account_id,tax_debit_account_id,tax_credit_account_id,effective_from,active FROM accounting_posting_profiles WHERE tenant_id=:t ORDER BY operation,effective_from DESC"), {"t": UUID(a.tenant_id)})).mappings().all()
    return [{k: (str(v) if isinstance(v, UUID) else v) for k, v in dict(r).items()} for r in rows]

@router.post("/treasury-accounts", status_code=201)
async def create_treasury(r: TreasuryAccountIn, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    _admin(a); tid = uuid4()
    await s.execute(text("INSERT INTO treasury_accounts(id,tenant_id,company_id,name,currency,ledger_account_id) VALUES(:id,:t,:c,:n,:cur,:l)"),
                    {"id": tid, "t": UUID(a.tenant_id), "c": r.company_id, "n": r.name, "cur": r.currency, "l": r.ledger_account_id})
    return {"id": str(tid)}
@router.get("/treasury-accounts")
async def list_treasury(a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    rows = (await s.execute(text("SELECT id,name,currency,ledger_account_id,active FROM treasury_accounts WHERE tenant_id=:t ORDER BY name"), {"t": UUID(a.tenant_id)})).mappings().all()
    return [{k: (str(v) if isinstance(v, UUID) else v) for k, v in dict(r).items()} for r in rows]

@router.post("/tax-rules", status_code=201)
async def create_tax_rule(r: TaxRuleIn, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    _admin(a); rid = uuid4()
    await s.execute(text("INSERT INTO tax_rules(id,tenant_id,company_id,code,rate,rounding_scale,effective_from) VALUES(:id,:t,:c,:code,:rate,:rs,:ef)"),
                    {"id": rid, "t": UUID(a.tenant_id), "c": r.company_id, "code": r.code, "rate": r.rate, "rs": r.rounding_scale, "ef": r.effective_from})
    return {"id": str(rid)}
@router.get("/tax-rules")
async def list_tax_rules(a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    rows = (await s.execute(text("SELECT id,code,rate,rounding_scale,effective_from,effective_to,active FROM tax_rules WHERE tenant_id=:t ORDER BY code,effective_from DESC"), {"t": UUID(a.tenant_id)})).mappings().all()
    return [{k: (str(v) if isinstance(v, (UUID, Decimal)) else v) for k, v in dict(r).items()} for r in rows]

@router.post("/document-sequences", status_code=201)
async def create_sequence(r: DocumentSequenceIn, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    _admin(a)
    res = await s.execute(text("""INSERT INTO document_sequences(tenant_id,company_id,document_type,series,next_value,padding)
        VALUES(:t,COALESCE(CAST(:c AS uuid),CAST('00000000-0000-0000-0000-000000000000' AS uuid)),:dt,:se,:st,:pad) ON CONFLICT DO NOTHING"""),
        {"t": UUID(a.tenant_id), "c": r.company_id, "dt": r.document_type, "se": r.series, "st": r.start, "pad": r.padding})
    if res.rowcount == 0: raise HTTPException(409, {"code": "SEQUENCE_ALREADY_EXISTS"})
    return {"document_type": r.document_type, "series": r.series, "next_value": r.start}
@router.get("/document-sequences")
async def list_sequences(a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    rows = (await s.execute(text("SELECT document_type,series,next_value,padding FROM document_sequences WHERE tenant_id=:t ORDER BY document_type,series"), {"t": UUID(a.tenant_id)})).mappings().all()
    return [dict(r) for r in rows]


class NeuralPolicyIn(BaseModel):
    agent: str = Field(min_length=1, max_length=120); purpose: str = Field(min_length=1, max_length=120); environment: str = Field(min_length=1, max_length=40)
    model_id: UUID; min_confidence: float = Field(ge=0, le=1); allowed_decisions: list[str] = Field(min_length=1, max_length=50); enabled: bool = True
class InferenceRouteIn(BaseModel):
    model_id: UUID; environment: str = Field(min_length=1, max_length=40); traffic_percent: float = Field(ge=0, le=100); active: bool = True
class RolloutPolicyIn(BaseModel):
    platform: str = Field(min_length=1, max_length=60); ring: str = Field(min_length=1, max_length=40); min_healthy_percent: float = Field(ge=0, le=100); max_failure_percent: float = Field(ge=0, le=100)
    max_concurrent: int = Field(default=1, ge=1, le=10000); require_attestation: bool = True; require_rollback_artifact: bool = True; enabled: bool = True

@router.put("/neural-policies", status_code=201)
async def put_neural_policy(r: NeuralPolicyIn, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    _admin(a)
    pid = (await s.execute(text("""INSERT INTO agent_neural_policies(tenant_id,agent,purpose,environment,model_id,min_confidence,allowed_decisions,enabled) VALUES(:t,:a,:p,:e,:m,:c,:d,:en)
        ON CONFLICT(tenant_id,agent,purpose,environment) DO UPDATE SET model_id=EXCLUDED.model_id,min_confidence=EXCLUDED.min_confidence,allowed_decisions=EXCLUDED.allowed_decisions,enabled=EXCLUDED.enabled RETURNING policy_id"""),
        {"t": UUID(a.tenant_id), "a": r.agent, "p": r.purpose, "e": r.environment, "m": r.model_id, "c": r.min_confidence, "d": sorted(set(r.allowed_decisions)), "en": r.enabled})).scalar_one()
    return {"policy_id": str(pid)}

@router.put("/inference-routes", status_code=201)
async def put_route(r: InferenceRouteIn, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    _admin(a)
    await s.execute(text("""INSERT INTO ml_inference_routes(tenant_id,model_id,environment,traffic_percent,active) VALUES(:t,:m,:e,:p,:ac)
        ON CONFLICT(tenant_id,model_id,environment) DO UPDATE SET traffic_percent=EXCLUDED.traffic_percent,active=EXCLUDED.active"""), {"t": UUID(a.tenant_id), "m": r.model_id, "e": r.environment, "p": r.traffic_percent, "ac": r.active})
    return {"model_id": str(r.model_id), "environment": r.environment, "traffic_percent": r.traffic_percent}

@router.put("/rollout-policies", status_code=201)
async def put_rollout(r: RolloutPolicyIn, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    _admin(a)
    await s.execute(text("""INSERT INTO edge_rollout_policies(tenant_id,platform,ring,min_healthy_percent,max_failure_percent,max_concurrent,require_attestation,require_rollback_artifact,enabled)
        VALUES(:t,:pl,:rg,:mh,:mf,:mc,:ra,:rr,:en) ON CONFLICT(tenant_id,platform,ring) DO UPDATE SET min_healthy_percent=EXCLUDED.min_healthy_percent,max_failure_percent=EXCLUDED.max_failure_percent,
        max_concurrent=EXCLUDED.max_concurrent,require_attestation=EXCLUDED.require_attestation,require_rollback_artifact=EXCLUDED.require_rollback_artifact,enabled=EXCLUDED.enabled"""),
        {"t": UUID(a.tenant_id), "pl": r.platform, "rg": r.ring, "mh": r.min_healthy_percent, "mf": r.max_failure_percent, "mc": r.max_concurrent, "ra": r.require_attestation, "rr": r.require_rollback_artifact, "en": r.enabled})
    return {"platform": r.platform, "ring": r.ring}
