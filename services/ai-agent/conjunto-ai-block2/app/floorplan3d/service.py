from __future__ import annotations
import os
import fitz
import cv2
import numpy as np
from .engine import get_engine
from .mesh_builder import SceneBuilder


class FloorPlan3DService:
    def __init__(self, output_dir: str, engine_name: str | None = None):
        self.output_dir = output_dir
        self.engine = get_engine(engine_name)
        self.builder = SceneBuilder()

    def process(
        self, path: str, plan_width_m: float, wall_height_m: float = 2.6
    ) -> dict:
        image = self._read(path)
        analysis = self.engine.analyze(image)
        glb, spec, scale = self.builder.build(
            analysis, plan_width_m, wall_height_m, self.output_dir
        )
        h, w = analysis.image_shape
        return {
            "job_id": os.path.splitext(os.path.basename(glb))[0],
            "model_url": "/models/" + os.path.basename(glb),
            "engine": analysis.engine_name,
            "duration_ms": 0,
            "scale_m_per_px": scale,
            "wall_height_m": wall_height_m,
            "image_shape": [h, w],
            "doors_count": len(analysis.doors),
            "windows_count": len(analysis.windows),
            "rooms_count": len(analysis.rooms),
            "labels_count": len(analysis.labels),
            "diagnostics": analysis.diagnostics,
            "scene": spec,
            "doors": [self._poly(d.polygon, d.confidence) for d in analysis.doors],
            "windows": [self._poly(d.polygon, d.confidence) for d in analysis.windows],
            "rooms": [
                {
                    "polygon": r.polygon.tolist(),
                    "label": r.label,
                    "area_m2": round(r.area_px * scale * scale, 2),
                    "confidence": r.confidence,
                }
                for r in analysis.rooms
            ],
            "labels": [
                {
                    "text": x.text,
                    "polygon": x.polygon.tolist(),
                    "confidence": x.confidence,
                }
                for x in analysis.labels
            ],
        }

    def _read(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext == ".pdf":
            doc = fitz.open(path)
            if not len(doc):
                raise ValueError("PDF sin páginas")
            page = doc[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, pix.n
            )
            if pix.n == 4:
                image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
            else:
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            return image
        image = cv2.imread(path)
        if image is None:
            raise ValueError("No se pudo leer el plano")
        return image

    @staticmethod
    def _poly(p, c):
        return {"polygon": p.tolist(), "confidence": c}
