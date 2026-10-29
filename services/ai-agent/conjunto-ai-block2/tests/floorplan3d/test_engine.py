import pytest
import cv2
import numpy as np
from app.floorplan3d.engine.heuristic_engine import HeuristicCVEngine


def _synthetic_page(skew_deg: float) -> np.ndarray:
    page = np.full((400, 600, 3), 255, np.uint8)
    for y in range(80, 320, 40):
        cv2.line(page, (60, y), (540, y), (0, 0, 0), 3)
    matrix = cv2.getRotationMatrix2D((300, 200), skew_deg, 1.0)
    return cv2.warpAffine(page, matrix, (600, 400), borderValue=(255, 255, 255))


def test_heuristic_extracts_rooms_from_clean_plan():
    image = np.ones((500, 700, 3), np.uint8) * 255
    cv2.rectangle(image, (30, 30), (670, 470), (0, 0, 0), 7)
    cv2.line(image, (350, 30), (350, 470), (0, 0, 0), 7)
    result = HeuristicCVEngine().analyze(image)
    assert result.image_shape == (500, 700)
    assert result.walls_mask.shape == (500, 700)
    assert len(result.rooms) >= 1
    assert result.engine_name == "heuristic-pro"


@pytest.mark.parametrize("skew_deg", [0.0, 3.0, -5.0])
def test_skew_is_reported_as_metadata_without_changing_geometry(skew_deg: float):
    image = _synthetic_page(skew_deg)

    result = HeuristicCVEngine().analyze(image)

    reported_skew = result.diagnostics["skew_deg"]
    assert isinstance(reported_skew, float)
    assert abs(abs(reported_skew) - abs(skew_deg)) < 1.0
    assert result.image_shape == image.shape[:2]
    assert result.walls_mask.shape == image.shape[:2]
