import hashlib
import pytest
from app.neural.runtime import NeuralRuntime, ModelSpec, NeuralRuntimeError


def test_missing_artifact_fails_closed(tmp_path):
    rt = NeuralRuntime(str(tmp_path))
    with pytest.raises(NeuralRuntimeError, match="model_artifact_not_found"):
        rt.register(ModelSpec("x", "1", "x.onnx", "0" * 64, {}, {}))


def test_path_escape_rejected(tmp_path):
    p = tmp_path.parent / "outside.onnx"
    p.write_bytes(b"x")
    rt = NeuralRuntime(str(tmp_path))
    with pytest.raises(NeuralRuntimeError, match="artifact_path_outside_model_root"):
        rt.register(
            ModelSpec(
                "x", "1", "../outside.onnx", hashlib.sha256(b"x").hexdigest(), {}, {}
            )
        )
