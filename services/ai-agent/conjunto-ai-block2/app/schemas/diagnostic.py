from pydantic import Field
from .common import AIRequest


class DiagnosticRequest(AIRequest):
    asset_id: str = Field(min_length=1, max_length=100)
    observation: str = Field(min_length=1, max_length=5000)
    tenant_id: str = Field(min_length=1, max_length=100)
