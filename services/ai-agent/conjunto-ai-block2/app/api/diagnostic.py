from fastapi import APIRouter
from app.agents.diagnostic import DiagnosticAgent
from app.providers.factory import build_provider
from app.schemas.diagnostic import DiagnosticRequest
from app.tools.bootstrap import build_tool_registry

router = APIRouter(tags=["diagnostic"])


@router.post("/diagnostic")
async def analyze_diagnostic(request: DiagnosticRequest):
    agent = DiagnosticAgent(build_tool_registry(), build_provider())
    return await agent.run(request)
