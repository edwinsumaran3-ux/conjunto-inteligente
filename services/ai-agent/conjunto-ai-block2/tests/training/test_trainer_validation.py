from pathlib import Path
import pytest
from app.training.mlp_trainer import train_mlp_npz, TrainingError


def test_missing_dataset_fails_closed(tmp_path: Path):
    with pytest.raises(TrainingError, match="DATASET_MISSING"):
        train_mlp_npz(tmp_path / "missing.npz", tmp_path / "out")
