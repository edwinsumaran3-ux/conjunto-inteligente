from __future__ import annotations
import hashlib
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModelSpec:
    name: str
    version: str
    artifact_uri: str
    sha256: str
    input_schema: dict
    output_schema: dict


class NeuralRuntimeError(RuntimeError):
    pass


class NeuralRuntime:
    """ONNX inference boundary with artifact integrity verification.

    The runtime never returns a synthetic prediction when a model is absent, invalid,
    or the artifact hash does not match the registered SHA-256.
    """

    def __init__(self, model_root: str | None = None):
        root = (
            model_root
            if model_root is not None
            else os.getenv("NEURAL_MODEL_ROOT", "models")
        )
        self.model_root = Path(root).resolve()
        self._sessions: dict[str, Any] = {}
        self._specs: dict[str, ModelSpec] = {}

    def register(self, spec: ModelSpec) -> None:
        if spec.artifact_uri.startswith(("http://", "https://", "s3://", "gs://")):
            raise NeuralRuntimeError("remote_artifact_requires_external_verified_fetch")
        path = (self.model_root / spec.artifact_uri).resolve()
        if self.model_root not in path.parents and path != self.model_root:
            raise NeuralRuntimeError("artifact_path_outside_model_root")
        if not path.is_file():
            raise NeuralRuntimeError("model_artifact_not_found")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest.lower() != spec.sha256.lower():
            raise NeuralRuntimeError("model_artifact_hash_mismatch")
        self._specs[f"{spec.name}:{spec.version}"] = spec

    def predict(self, *, model_key: str, inputs: dict[str, Any]) -> dict[str, Any]:
        spec = self._specs.get(model_key)
        if not spec:
            raise NeuralRuntimeError("model_not_registered")
        if not self._sessions.get(model_key):
            try:
                import onnxruntime as ort
            except ImportError as exc:
                raise NeuralRuntimeError("onnxruntime_not_installed") from exc
            path = (self.model_root / spec.artifact_uri).resolve()
            self._sessions[model_key] = ort.InferenceSession(
                str(path), providers=["CPUExecutionProvider"]
            )
        session = self._sessions[model_key]
        missing = [k for k in spec.input_schema.get("required", []) if k not in inputs]
        if missing:
            raise NeuralRuntimeError("missing_model_inputs:" + ",".join(missing))
        feed = {k: inputs[k] for k in session.get_inputs() if k.name in inputs}
        if len(feed) != len(session.get_inputs()):
            raise NeuralRuntimeError("model_input_contract_mismatch")
        started = time.perf_counter()
        outputs = session.run(None, feed)
        latency = int((time.perf_counter() - started) * 1000)
        names = [x.name for x in session.get_outputs()]
        return {
            "model": model_key,
            "outputs": {
                n: o.tolist() if hasattr(o, "tolist") else o
                for n, o in zip(names, outputs)
            },
            "latency_ms": latency,
        }
