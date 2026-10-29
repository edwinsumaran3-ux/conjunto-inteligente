from pathlib import Path
from backend.app.modules.model_ops.service import verify_artifact, validate_manifest

def test_manifest_requires_provenance():
    ok, reason = validate_manifest({'model_name':'x','model_version':'1','framework':'torch','format':'onnx'})
    assert not ok and 'missing_manifest_fields' in reason

def test_artifact_hash(tmp_path: Path):
    p=tmp_path/'m.onnx'; p.write_bytes(b'abc')
    import hashlib
    h=hashlib.sha256(b'abc').hexdigest()
    r=verify_artifact(p,h)
    assert r.verified and r.size_bytes==3
