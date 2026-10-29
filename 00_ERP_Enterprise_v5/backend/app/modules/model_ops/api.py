from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from backend.app.api.deps import AuthContext, get_auth_context
from .service import verify_artifact, validate_manifest

router=APIRouter(prefix='/model-ops',tags=['model-ops'])
class VerifyArtifactRequest(BaseModel):
    path: str = Field(min_length=1,max_length=1000)
    sha256: str = Field(pattern=r'^[0-9a-fA-F]{64}$')
    max_bytes: int = Field(default=2*1024**3,gt=0)
class ManifestRequest(BaseModel): manifest: dict

@router.post('/artifacts/verify')
def verify(req:VerifyArtifactRequest, auth:AuthContext=Depends(get_auth_context)):
    # The API never dereferences remote URIs and rejects path traversal by requiring an absolute local artifact path.
    p=Path(req.path).resolve()
    root=Path('/var/lib/conjunto/models').resolve()
    try: p.relative_to(root)
    except ValueError: raise HTTPException(400,'ARTIFACT_PATH_OUTSIDE_MODEL_ROOT')
    r=verify_artifact(p,req.sha256,max_bytes=req.max_bytes)
    return r.__dict__

@router.post('/manifests/validate')
def manifest(req:ManifestRequest, auth:AuthContext=Depends(get_auth_context)):
    ok,reason=validate_manifest(req.manifest)
    if not ok: raise HTTPException(422,reason)
    return {'valid':True,'reason':reason}
