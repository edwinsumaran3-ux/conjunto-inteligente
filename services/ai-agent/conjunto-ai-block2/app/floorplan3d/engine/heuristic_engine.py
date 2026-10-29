from __future__ import annotations
import cv2
import numpy as np
from .base import Detection, FloorPlanAIEngine, FloorPlanAnalysis, OCRLabel, RoomSegment


class HeuristicCVEngine(FloorPlanAIEngine):
    """Deterministic CV pipeline tuned for architectural plans.

    It estimates skew without rotating the image, then performs contrast
    normalization, directional wall extraction, room segmentation, geometric
    opening detection and OCR. The skew angle is informational; image pixels
    and overlay coordinates remain in their original geometry.
    """

    name = "heuristic-pro"

    def __init__(self, min_wall_area: int = 80):
        self.min_wall_area = min_wall_area

    def analyze(self, image_bgr: np.ndarray) -> FloorPlanAnalysis:
        if image_bgr is None or image_bgr.size == 0:
            raise ValueError("Imagen de plano vacía")
        image = self._normalise(image_bgr)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        walls = self._detect_walls(gray)
        doors = self._detect_doors(gray, walls)
        windows = self._detect_windows(gray, walls)
        rooms = self._segment_rooms(walls)
        labels = self._ocr(image, rooms)
        diagnostics = {
            "wall_coverage": float(np.count_nonzero(walls)) / float(walls.size),
            "skew_deg": self._estimate_skew(gray),
            "wall_components": int(cv2.connectedComponents(walls)[0] - 1),
        }
        return FloorPlanAnalysis(
            walls_mask=walls,
            doors=doors,
            windows=windows,
            rooms=rooms,
            labels=labels,
            image_shape=gray.shape,
            engine_name=self.name,
            diagnostics=diagnostics,
        )

    def _normalise(self, image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # CLAHE keeps faint scanned walls readable without over-amplifying text.
        clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        out = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
        return out

    def _estimate_skew(self, gray: np.ndarray) -> float:
        edges = cv2.Canny(gray, 50, 150)
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 120)
        if lines is None:
            return 0.0
        angles = []
        for rho, theta in lines[:80, 0]:
            deg = theta * 180.0 / np.pi - 90.0
            if -15 < deg < 15:
                angles.append(deg)
        return float(np.median(angles)) if angles else 0.0

    def _detect_walls(self, gray: np.ndarray) -> np.ndarray:
        bw = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 7
        )
        # Directional closing connects wall runs while suppressing most text.
        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 2))
        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 11))
        horizontal = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, h_kernel, iterations=1)
        vertical = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, v_kernel, iterations=1)
        directional = cv2.bitwise_or(horizontal, vertical)
        thick = cv2.morphologyEx(
            directional, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=2
        )
        num, labels, stats, _ = cv2.connectedComponentsWithStats(thick, connectivity=8)
        clean = np.zeros_like(thick)
        for i in range(1, num):
            area = stats[i, cv2.CC_STAT_AREA]
            width = stats[i, cv2.CC_STAT_WIDTH]
            height = stats[i, cv2.CC_STAT_HEIGHT]
            if area >= self.min_wall_area and (width >= 14 or height >= 14):
                clean[labels == i] = 255
        return clean

    def _detect_doors(self, gray: np.ndarray, walls: np.ndarray) -> list[Detection]:
        edges = cv2.Canny(gray, 40, 120)
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180, threshold=28, minLineLength=14, maxLineGap=4
        )
        out: list[Detection] = []
        if lines is None:
            return out
        # A door candidate is a short line close to a wall with an opening nearby.
        dist = cv2.distanceTransform(255 - walls, cv2.DIST_L2, 3)
        for raw in lines[:600]:
            x1, y1, x2, y2 = raw.reshape(4)
            length = float(np.hypot(x2 - x1, y2 - y1))
            if not 12 <= length <= 120:
                continue
            mx, my = int((x1 + x2) / 2), int((y1 + y2) / 2)
            if not (0 <= my < dist.shape[0] and 0 <= mx < dist.shape[1]):
                continue
            # Door swings create a compact arc/line cluster away from the wall.
            if dist[my, mx] > 18:
                continue
            pad = max(5, int(length * 0.22))
            poly = np.array(
                [
                    [x1 - pad, y1 - pad],
                    [x2 + pad, y2 + pad],
                    [x2 + pad, y2 + pad],
                    [x1 - pad, y1 - pad],
                ],
                dtype=np.float32,
            )
            # Make a valid rectangle around the segment.
            dx, dy = x2 - x1, y2 - y1
            n = np.array([-dy, dx], dtype=np.float32)
            n /= np.linalg.norm(n) + 1e-6
            half = min(6.0, max(3.0, length * 0.08))
            p1 = np.array([x1, y1], dtype=np.float32)
            p2 = np.array([x2, y2], dtype=np.float32)
            poly = np.array(
                [p1 + n * half, p2 + n * half, p2 - n * half, p1 - n * half],
                dtype=np.float32,
            )
            if not any(
                np.linalg.norm(poly.mean(0) - d.polygon.mean(0)) < 12 for d in out
            ):
                out.append(Detection("door", poly, 0.66, {"length_px": length}))
        return out[:120]

    def _detect_windows(self, gray: np.ndarray, walls: np.ndarray) -> list[Detection]:
        lines = cv2.HoughLinesP(
            cv2.Canny(gray, 50, 150),
            1,
            np.pi / 180,
            threshold=45,
            minLineLength=28,
            maxLineGap=3,
        )
        out: list[Detection] = []
        if lines is None:
            return out
        segments = []
        for raw in lines[:1000]:
            x1, y1, x2, y2 = raw.reshape(4)
            angle = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1))) % 180
            if min(angle, 180 - angle) > 8 and abs(angle - 90) > 8:
                continue
            length = float(np.hypot(x2 - x1, y2 - y1))
            if length >= 30:
                segments.append((x1, y1, x2, y2, length, angle))
        for i, a in enumerate(segments):
            x1, y1, x2, y2, l1, ang = a
            for b in segments[i + 1 : i + 40]:
                x3, y3, x4, y4, l2, ang2 = b
                if abs(ang - ang2) > 5:
                    continue
                d = abs((x3 - x1) * (y2 - y1) - (y3 - y1) * (x2 - x1)) / (l1 + 1e-6)
                if 2 <= d <= 10 and abs(l1 - l2) / max(l1, l2) < 0.45:
                    poly = np.array(
                        [[x1, y1], [x2, y2], [x4, y4], [x3, y3]], dtype=np.float32
                    )
                    if not any(
                        np.linalg.norm(poly.mean(0) - w.polygon.mean(0)) < 15
                        for w in out
                    ):
                        out.append(
                            Detection(
                                "window", poly, 0.78, {"length_px": (l1 + l2) / 2}
                            )
                        )
                    break
        return out[:160]

    def _segment_rooms(self, walls: np.ndarray) -> list[RoomSegment]:
        closed = cv2.morphologyEx(
            walls, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8), iterations=2
        )
        free = cv2.bitwise_not(closed)
        # Remove the exterior connected component by flood-fill from borders.
        exterior = free.copy()
        h, w = free.shape
        mask = np.zeros((h + 2, w + 2), np.uint8)
        flood = exterior.copy()
        cv2.floodFill(flood, mask, (0, 0), 0)
        num, labels, stats, _ = cv2.connectedComponentsWithStats(flood, connectivity=4)
        out = []
        for i in range(1, num):
            area = int(stats[i, cv2.CC_STAT_AREA])
            if area < 600:
                continue
            comp = (labels == i).astype(np.uint8) * 255
            contours, _ = cv2.findContours(
                comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            if not contours:
                continue
            c = max(contours, key=cv2.contourArea)
            if cv2.contourArea(c) < 500:
                continue
            approx = cv2.approxPolyDP(c, 3.0, True).reshape(-1, 2).astype(np.float32)
            if len(approx) >= 3:
                out.append(RoomSegment(approx, "room", float(area), 0.92))
        return sorted(out, key=lambda r: r.area_px, reverse=True)[:250]

    def _ocr(self, image: np.ndarray, rooms: list[RoomSegment]) -> list[OCRLabel]:
        try:
            import pytesseract

            data = pytesseract.image_to_data(
                image,
                config="--psm 11",
                output_type=pytesseract.Output.DICT,
                lang="eng",
            )
        except Exception:
            return []
        labels = []
        for i, text in enumerate(data.get("text", [])):
            text = " ".join(str(text).split())
            conf = (
                float(data["conf"][i])
                if str(data["conf"][i]).strip() not in ("", "-1")
                else -1
            )
            if len(text) < 2 or conf < 45:
                continue
            x, y, w, h = [int(data[k][i]) for k in ("left", "top", "width", "height")]
            poly = np.array(
                [[x, y], [x + w, y], [x + w, y + h], [x, y + h]], dtype=np.float32
            )
            labels.append(OCRLabel(text, poly, conf / 100.0))
        # Prefer labels whose centroid lies inside a detected room.
        filtered = []
        for label in labels:
            cx, cy = label.polygon.mean(0)
            if any(
                cv2.pointPolygonTest(
                    r.polygon.astype(np.float32), (float(cx), float(cy)), False
                )
                >= 0
                for r in rooms
            ):
                filtered.append(label)
        return filtered[:200]
