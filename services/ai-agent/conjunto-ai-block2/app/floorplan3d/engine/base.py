from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
import numpy as np


@dataclass
class Detection:
    kind: str
    polygon: np.ndarray
    confidence: float = 1.0
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class RoomSegment:
    polygon: np.ndarray
    label: str = "room"
    area_px: float = 0.0
    confidence: float = 1.0


@dataclass
class OCRLabel:
    text: str
    polygon: np.ndarray
    confidence: float = 0.0


@dataclass
class FloorPlanAnalysis:
    walls_mask: np.ndarray
    doors: list[Detection] = field(default_factory=list)
    windows: list[Detection] = field(default_factory=list)
    rooms: list[RoomSegment] = field(default_factory=list)
    labels: list[OCRLabel] = field(default_factory=list)
    scale_m_per_px: float | None = None
    image_shape: tuple[int, int] = (0, 0)
    engine_name: str = "unknown"
    diagnostics: dict[str, Any] = field(default_factory=dict)


class FloorPlanAIEngine(ABC):
    name = "base"

    @abstractmethod
    def analyze(self, image_bgr: np.ndarray) -> FloorPlanAnalysis:
        raise NotImplementedError

    def warmup(self) -> None:
        return
