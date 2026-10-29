from __future__ import annotations
import os
import uuid
import cv2
import numpy as np
import trimesh
from typing import Any
from .engine.base import FloorPlanAnalysis


class SceneBuilder:
    """Dependency-light 3D builder.

    It uses architectural line primitives rather than a fragile polygon
    triangulator, which makes the converter deployable in a minimal container.
    The returned scene spec is also consumed directly by the browser WebGL
    viewer, while GLB remains the portable interchange format.
    """

    def build(
        self,
        analysis: FloorPlanAnalysis,
        width_m: float,
        height_m: float,
        output_dir: str,
    ):
        h, w = analysis.image_shape
        scale = width_m / max(w, 1)
        wall_h = max(2.1, float(height_m))
        wall_t = max(0.07, min(0.28, scale * 8))
        scene = trimesh.Scene()
        spec: list[dict[str, Any]] = []
        # Floor slab
        floor = self._box(
            (width_m, max(0.5, h * scale), 0.08),
            (width_m / 2, -(h * scale) / 2, -0.04),
            [30, 45, 58, 255],
        )
        scene.add_geometry(floor, node_name="floor")
        spec.append(
            {
                "type": "box",
                "size": [width_m, max(0.5, h * scale), 0.08],
                "position": [width_m / 2, -(h * scale) / 2, -0.04],
                "color": [0.12, 0.18, 0.23, 1],
                "kind": "floor",
            }
        )
        lines = cv2.HoughLinesP(
            analysis.walls_mask,
            1,
            np.pi / 180,
            threshold=24,
            minLineLength=max(18, int(w * 0.015)),
            maxLineGap=8,
        )
        used: list[tuple[float, float, float]] = []
        if lines is not None:
            for raw in lines[:800]:
                x1, y1, x2, y2 = map(int, raw[0])
                length_px = float(np.hypot(x2 - x1, y2 - y1))
                if length_px < 20:
                    continue
                # suppress duplicates by midpoint/orientation
                angle = (
                    round(float(np.degrees(np.arctan2(y2 - y1, x2 - x1))) % 180 / 4) * 4
                )
                mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                if any(
                    abs(mx - u[0]) < 10
                    and abs(my - u[1]) < 10
                    and abs(angle - u[2]) < 8
                    for u in used
                ):
                    continue
                used.append((mx, my, angle))
                x = mx * scale
                y = -my * scale
                length = length_px * scale
                dx = (x2 - x1) / max(length_px, 1)
                dy = (y2 - y1) / max(length_px, 1)
                cx = x
                cy = y
                # Box local X follows line direction.
                box = self._box(
                    (length, wall_t, wall_h), (0, 0, 0), [205, 218, 228, 255]
                )
                theta = np.arctan2(-dy, dx)
                box.apply_transform(
                    trimesh.transformations.rotation_matrix(theta, [0, 0, 1])
                )
                box.apply_translation((cx, cy, wall_h / 2))
                scene.add_geometry(box, node_name=f"wall-{len(used)}")
                spec.append(
                    {
                        "type": "box",
                        "size": [length, wall_t, wall_h],
                        "position": [cx, cy, wall_h / 2],
                        "rotation": float(theta),
                        "color": [0.80, 0.85, 0.89, 1],
                        "kind": "wall",
                    }
                )
        # Openings become visible accent volumes instead of being filled by walls.
        for kind, items, z, color in [
            ("door", analysis.doors, 0.95, [0.93, 0.58, 0.22, 0.8]),
            ("window", analysis.windows, 1.15, [0.2, 0.78, 0.95, 0.65]),
        ]:
            for i, d in enumerate(items[:180]):
                p = d.polygon
                cx, cy = p[:, 0].mean() * scale, -p[:, 1].mean() * scale
                minx, maxx = p[:, 0].min() * scale, p[:, 0].max() * scale
                miny, maxy = p[:, 1].min() * scale, p[:, 1].max() * scale
                sx = max(0.08, maxx - minx)
                sy = max(0.05, maxy - miny)
                box = self._box(
                    (sx, sy, 0.08), (cx, cy, z), [int(c * 255) for c in color]
                )
                scene.add_geometry(box, node_name=f"{kind}-{i}")
                spec.append(
                    {
                        "type": "box",
                        "size": [sx, sy, 0.08],
                        "position": [cx, cy, z],
                        "color": color,
                        "kind": kind,
                    }
                )
        os.makedirs(output_dir, exist_ok=True)
        job_id = uuid.uuid4().hex
        path = os.path.join(output_dir, f"{job_id}.glb")
        scene.export(path, file_type="glb")
        return path, spec, scale

    @staticmethod
    def _box(size, position, color):
        m = trimesh.creation.box(extents=size)
        m.apply_translation(position)
        m.visual = trimesh.visual.ColorVisuals(
            mesh=m, face_colors=np.tile(color, (len(m.faces), 1))
        )
        return m
