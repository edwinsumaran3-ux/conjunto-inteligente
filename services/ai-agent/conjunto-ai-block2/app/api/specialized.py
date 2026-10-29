import secrets
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from uuid import UUID
from app.agents.specialized import SpecializedAgent, SpecializedRequest
from app.providers.factory import get_provider
from app.governance.service import AgentGovernance

router = APIRouter()


class SpecializedBody(BaseModel):
    request_id: UUID
    tenant_id: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=20000)


@router.post("/{agent}")
async def analyze(
    agent: str, body: SpecializedBody, authorization: str | None = Header(default=None)
):
    from app.core.config import get_settings

    expected = get_settings().internal_service_token
    if expected and not authorization:
        raise HTTPException(status_code=401, detail="missing service authorization")
    if expected and (
        not authorization
        or not secrets.compare_digest(authorization, f"Bearer {expected}")
    ):
        raise HTTPException(status_code=403, detail="invalid service authorization")
    try:
        request = SpecializedRequest(
            request_id=body.request_id, tenant_id=body.tenant_id, message=body.message
        )
        governance = AgentGovernance()
        execution = governance.start(
            request_id=request.request_id,
            trace_id=None,
            tenant_id=request.tenant_id,
            agent=agent,
            action="analyze",
            payload={"message": request.message},
        )
        result = await SpecializedAgent(agent, get_provider()).run(request)
        result.requires_human_review = (
            result.requires_human_review or execution.requires_human_review
        )
        result.warnings.append(f"governance_execution_id={execution.execution_id}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.model_dump()
