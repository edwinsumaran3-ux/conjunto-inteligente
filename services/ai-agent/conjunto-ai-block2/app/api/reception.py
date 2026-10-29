from fastapi import APIRouter
from app.agents.reception import ReceptionAgent
from app.providers.factory import build_provider
from app.schemas.reception import ReceptionRequest
from app.tools.bootstrap import build_tool_registry

router = APIRouter(tags=["reception"])


@router.post("/reception")
async def analyze_reception(request: ReceptionRequest):
    agent = ReceptionAgent(build_tool_registry(), build_provider())
    return await agent.run(request)
