from app.floorplan3d.coverage import analyse_coverage


def test_coverage_returns_percentages():
    result = analyse_coverage(
        [{"id": "CAM-1", "x": 5, "y": -5, "range": 8, "fov": 90, "heading": 0}],
        [],
        20,
        20,
        0.5,
    )
    assert 0 <= result["coverage_percent"] <= 100
    assert 0 <= result["blind_percent"] <= 100
