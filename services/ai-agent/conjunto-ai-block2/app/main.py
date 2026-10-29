from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.health import router as health_router
from app.api.reception import router as reception_router
from app.api.diagnostic import router as diagnostic_router
from app.api.procurement import router as procurement_router
from app.api.specialized import router as specialized_router
from app.core.config import get_settings
from app.floorplan3d.router import router as floorplan3d_router
from app.api.neural import router as neural_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.service_name = get_settings().service_name
    yield


app = FastAPI(
    title="Conjunto Intelligent AI Orchestrator",
    version="2.0.0",
    lifespan=lifespan,
)
app.include_router(health_router)
app.include_router(reception_router, prefix="/analyze")
app.include_router(diagnostic_router, prefix="/analyze")
app.include_router(procurement_router, prefix="/procurement")
app.include_router(specialized_router, prefix="/analyze")
app.include_router(floorplan3d_router)
app.include_router(neural_router)
