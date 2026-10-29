import os
from .heuristic_engine import HeuristicCVEngine
from .base import FloorPlanAIEngine

ENGINES: dict[str, type[FloorPlanAIEngine]] = {"heuristic": HeuristicCVEngine}
NEURAL_AVAILABLE = False
try:
    from .neural_engine import NeuralSegmentationEngine
    import onnxruntime  # noqa: F401

    ENGINES["neural"] = NeuralSegmentationEngine
    NEURAL_AVAILABLE = True
except Exception:
    pass


def get_engine(name=None):
    name = name or os.getenv("FLOORPLAN_ENGINE", "heuristic")
    if name not in ENGINES:
        raise RuntimeError(
            f"Motor {name!r} no disponible. Disponibles: {list(ENGINES)}"
        )
    return ENGINES[name]()
