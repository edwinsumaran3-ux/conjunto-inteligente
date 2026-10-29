from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import numpy as np


@dataclass(frozen=True)
class TrainingResult:
    artifact: Path
    sha256: str
    metrics: dict


class TrainingError(RuntimeError):
    pass


def train_mlp_npz(
    dataset: Path, output_dir: Path, *, epochs: int = 20, seed: int = 42
) -> TrainingResult:
    """Train a real PyTorch MLP from a versioned NPZ dataset and export ONNX.

    Expected arrays: X_train, y_train, X_valid, y_valid. The function fails closed
    when torch/export dependencies are unavailable; it never fabricates metrics.
    """
    if not dataset.is_file():
        raise TrainingError("DATASET_MISSING")
    try:
        import torch
        from torch import nn
    except Exception as exc:
        raise TrainingError("TORCH_UNAVAILABLE") from exc
    data = np.load(dataset)
    required = ("X_train", "y_train", "X_valid", "y_valid")
    if any(k not in data for k in required):
        raise TrainingError("DATASET_SCHEMA_INVALID")
    Xtr = np.asarray(data["X_train"], dtype=np.float32)
    ytr = np.asarray(data["y_train"], dtype=np.float32)
    Xv = np.asarray(data["X_valid"], dtype=np.float32)
    yv = np.asarray(data["y_valid"], dtype=np.float32)
    if Xtr.ndim != 2 or Xv.ndim != 2 or Xtr.shape[1] != Xv.shape[1]:
        raise TrainingError("FEATURE_SHAPE_INVALID")
    if len(Xtr) != len(ytr) or len(Xv) != len(yv):
        raise TrainingError("LABEL_SHAPE_INVALID")
    torch.manual_seed(seed)
    np.random.seed(seed)
    model = nn.Sequential(
        nn.Linear(Xtr.shape[1], 64),
        nn.ReLU(),
        nn.Linear(64, 32),
        nn.ReLU(),
        nn.Linear(32, 1),
    )
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()
    tx = torch.from_numpy(Xtr)
    ty = torch.from_numpy(ytr.reshape(-1, 1))
    model.train()
    for _ in range(max(1, epochs)):
        opt.zero_grad()
        loss = loss_fn(model(tx), ty)
        loss.backward()
        opt.step()
    model.eval()
    with torch.no_grad():
        pred = model(torch.from_numpy(Xv)).numpy().reshape(-1)
    mse = float(np.mean((pred - yv.reshape(-1)) ** 2))
    mae = float(np.mean(np.abs(pred - yv.reshape(-1))))
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = output_dir / "model.onnx"
    torch.onnx.export(
        model,
        torch.from_numpy(Xtr[:1]),
        artifact,
        input_names=["features"],
        output_names=["prediction"],
        opset_version=17,
    )
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    metrics = {
        "validation_mse": mse,
        "validation_mae": mae,
        "epochs": epochs,
        "seed": seed,
        "samples_train": len(Xtr),
        "samples_valid": len(Xv),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "format": "onnx",
                "framework": "torch",
                "dataset_hash": hashlib.sha256(dataset.read_bytes()).hexdigest(),
                "artifact_sha256": digest,
                "metrics": metrics,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return TrainingResult(artifact, digest, metrics)
