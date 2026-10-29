from __future__ import annotations
import os
import cv2
import numpy as np
from .base import Detection, FloorPlanAIEngine, FloorPlanAnalysis, RoomSegment

try:
    import onnxruntime as ort
except ImportError:
    ort = None


class NeuralSegmentationEngine(FloorPlanAIEngine):
    name = "neural-unet"
    INPUT_SIZE = (512, 512)

    def __init__(self, model_path=None):
        if ort is None:
            raise RuntimeError("onnxruntime no está instalado")
        self.model_path = model_path or os.getenv("ONNX_MODEL_PATH")
        if not self.model_path or not os.path.exists(self.model_path):
            raise RuntimeError("ONNX_MODEL_PATH inválido")
        self.session = ort.InferenceSession(
            self.model_path, providers=["CUDAExecutionProvider", "CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

    def analyze(self, image_bgr):
        h, w = image_bgr.shape[:2]
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        x = cv2.resize(rgb, self.INPUT_SIZE).astype(np.float32) / 255.0
        x = (x - np.array([0.485, 0.456, 0.406], np.float32)) / np.array(
            [0.229, 0.224, 0.225], np.float32
        )
        x = x.transpose(2, 0, 1)[None]
        logits = self.session.run([self.output_name], {self.input_name: x})[0]
        pred = np.argmax(logits, axis=1)[0].astype(np.uint8)
        pred = cv2.resize(pred, (w, h), interpolation=cv2.INTER_NEAREST)
        walls = (pred == 1).astype(np.uint8) * 255
        return FloorPlanAnalysis(
            walls_mask=walls,
            doors=self._detections(pred == 2, "door"),
            windows=self._detections(pred == 3, "window"),
            rooms=self._rooms(pred == 4),
            image_shape=(h, w),
            engine_name=self.name,
        )

    @staticmethod
    def _detections(mask, kind):
        cs, _ = cv2.findContours(
            mask.astype(np.uint8) * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        out = []
        for c in cs:
            if cv2.contourArea(c) < 50:
                continue
            p = cv2.approxPolyDP(c, 2, True).reshape(-1, 2).astype(np.float32)
            if len(p) >= 3:
                out.append(Detection(kind, p, 0.9))
        return out

    @staticmethod
    def _rooms(mask):
        cs, _ = cv2.findContours(
            mask.astype(np.uint8) * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        out = []
        for c in cs:
            a = float(cv2.contourArea(c))
            if a < 300:
                continue
            p = cv2.approxPolyDP(c, 3, True).reshape(-1, 2).astype(np.float32)
            if len(p) >= 3:
                out.append(RoomSegment(p, "room", a, 0.9))
        return out
