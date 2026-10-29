from __future__ import annotations
import math
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union


def analyse_coverage(
    cameras: list[dict],
    wall_polygons: list[list[list[float]]],
    width_m: float,
    height_m: float,
    resolution: float = 0.5,
) -> dict:
    walls = []
    for pts in wall_polygons:
        if len(pts) >= 3:
            try:
                walls.append(Polygon(pts).buffer(0))
            except Exception:
                pass
    wall_union = unary_union(walls) if walls else None
    minx, miny = 0.0, -height_m
    covered = 0
    total = 0
    camera_stats = []
    # Grid sampling is deterministic and fast enough for an interactive analysis.
    y = miny
    for _ in range(int(height_m / resolution) + 1):
        x = minx
        for _ in range(int(width_m / resolution) + 1):
            total += 1
            visible = False
            for cam in cameras:
                cx, cy = float(cam.get("x", 0)), float(cam.get("y", 0))
                rng = float(cam.get("range", 8))
                fov = float(cam.get("fov", 70))
                heading = float(cam.get("heading", 0))
                dx = x - cx
                dy = y - cy
                dist = math.hypot(dx, dy)
                if dist > rng or dist < 0.1:
                    continue
                bearing = math.degrees(math.atan2(dy, dx))
                delta = ((bearing - heading + 180) % 360) - 180
                if abs(delta) > fov / 2:
                    continue
                ray = LineString([(cx, cy), (x, y)])
                if wall_union is not None and ray.crosses(wall_union):
                    continue
                visible = True
                break
            if visible:
                covered += 1
            x += resolution
        y += resolution
    coverage = covered / max(total, 1) * 100
    for i, cam in enumerate(cameras):
        camera_stats.append(
            {
                "id": cam.get("id", f"cam-{i+1}"),
                "coverage_weight": round(coverage / max(len(cameras), 1), 2),
            }
        )
    return {
        "coverage_percent": round(coverage, 2),
        "blind_percent": round(100 - coverage, 2),
        "samples": total,
        "cameras": camera_stats,
    }
