from fastapi import APIRouter, Response, status
from app.core.config import get_settings
from app.integrations.core_client import CoreClient

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.service_name,
        "environment": settings.environment,
    }


@router.get("/ready")
async def ready(response: Response):
    core_available = await CoreClient().health()
    if not core_available:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "degraded", "ready": False, "dependencies": {"core": False}}
    return {"status": "ready", "ready": True, "dependencies": {"core": True}}
