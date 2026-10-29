from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.neural.runtime import NeuralRuntime, NeuralRuntimeError, ModelSpec

router = APIRouter(prefix="/neural", tags=["neural"])
runtime = NeuralRuntime()


class Register(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=64)
    artifact_uri: str
    sha256: str = Field(pattern="^[0-9a-fA-F]{64}$")
    input_schema: dict = {}
    output_schema: dict = {}


class Predict(BaseModel):
    model_key: str
    inputs: dict


@router.post("/register")
def register(req: Register):
    try:
        runtime.register(
            ModelSpec(
                req.name,
                req.version,
                req.artifact_uri,
                req.sha256,
                req.input_schema,
                req.output_schema,
            )
        )
    except NeuralRuntimeError as e:
        raise HTTPException(422, detail=str(e))
    return {"status": "registered", "model_key": f"{req.name}:{req.version}"}


@router.post("/predict")
def predict(req: Predict):
    try:
        return runtime.predict(model_key=req.model_key, inputs=req.inputs)
    except NeuralRuntimeError as e:
        raise HTTPException(409, detail=str(e))
