from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import hashlib, json

@dataclass(frozen=True)
class ArtifactVerification:
    verified: bool
    sha256: str
    size_bytes: int
    reason: str

def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    h = hashlib.sha256()
    with path.open('rb') as f:
        while chunk := f.read(chunk_size): h.update(chunk)
    return h.hexdigest()

def verify_artifact(path: Path, expected_sha256: str, *, max_bytes: int = 2 * 1024**3) -> ArtifactVerification:
    if not expected_sha256 or len(expected_sha256) != 64:
        return ArtifactVerification(False, '', 0, 'invalid_expected_sha256')
    if not path.is_file(): return ArtifactVerification(False, '', 0, 'artifact_missing')
    size = path.stat().st_size
    if size > max_bytes: return ArtifactVerification(False, '', size, 'artifact_too_large')
    actual = sha256_file(path)
    return ArtifactVerification(actual.lower() == expected_sha256.lower(), actual, size, 'ok' if actual.lower() == expected_sha256.lower() else 'sha256_mismatch')

def validate_manifest(manifest: dict) -> tuple[bool,str]:
    required = ('model_name','model_version','framework','input_schema_hash','output_schema_hash','dataset_hash')
    missing = [k for k in required if not manifest.get(k)]
    if missing: return False, 'missing_manifest_fields:' + ','.join(missing)
    if manifest.get('format') not in ('onnx','json_weights'): return False, 'unsupported_model_format'
    return True, 'ok'
