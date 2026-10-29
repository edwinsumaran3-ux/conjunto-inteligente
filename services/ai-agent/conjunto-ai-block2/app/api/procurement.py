from fastapi import APIRouter
from app.agents.procurement import ProcurementAgent
from app.policies.engine import PolicyEngine
from app.providers.factory import build_provider
from app.schemas.procurement import ProcurementRequest

router = APIRouter(tags=["procurement"])


@router.post("/prepare")
async def prepare_procurement(request: ProcurementRequest):
    agent = ProcurementAgent(PolicyEngine(), build_provider())
    return await agent.run(request)
