from __future__ import annotations
import os
import uuid
import shutil
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from .service import FloorPlan3DService
from .engine.registry import ENGINES
from .coverage import analyse_coverage

router = APIRouter(prefix="/floorplan3d", tags=["floorplan3d"])
UPLOAD_DIR = os.getenv("FLOORPLAN_UPLOAD_DIR", "/tmp/floorplan3d/uploads")
OUTPUT_DIR = os.getenv("FLOORPLAN_OUTPUT_DIR", "/tmp/floorplan3d/outputs")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


class CoverageRequest(BaseModel):
    cameras: list[dict] = Field(default_factory=list)
    walls: list[list[list[float]]] = Field(default_factory=list)
    width_m: float = 20
    height_m: float = 20
    resolution: float = 0.5


@router.get("/engines")
def engines():
    return {
        "available": list(ENGINES.keys()),
        "active": os.getenv("FLOORPLAN_ENGINE", "heuristic"),
    }


@router.post("/convert")
async def convert(
    file: UploadFile = File(...),
    plan_width_m: float = Form(20.0),
    wall_height_m: float = Form(2.6),
    engine: str | None = Form(None),
):
    allowed = {"image/png", "image/jpeg", "image/webp", "application/pdf"}
    if file.content_type not in allowed:
        raise HTTPException(400, "Formato no soportado. Usa PDF, PNG, JPG o WEBP.")
    ext = os.path.splitext(file.filename or "plan.png")[1].lower() or ".png"
    src = os.path.join(UPLOAD_DIR, uuid.uuid4().hex + ext)
    with open(src, "wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        result = FloorPlan3DService(OUTPUT_DIR, engine).process(
            src, max(0.5, plan_width_m), max(2.0, wall_height_m)
        )
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Conversión 3D falló: {e}")


@router.post("/coverage")
def coverage(req: CoverageRequest):
    return analyse_coverage(
        req.cameras, req.walls, req.width_m, req.height_m, req.resolution
    )


@router.get("/models/{model_name}")
def model(model_name: str):
    path = os.path.join(OUTPUT_DIR, os.path.basename(model_name))
    if not os.path.exists(path):
        raise HTTPException(404, "Modelo no encontrado")
    return FileResponse(
        path, media_type="model/gltf-binary", filename=os.path.basename(path)
    )
