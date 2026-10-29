from pydantic import Field
from .common import AIRequest


class ReceptionRequest(AIRequest):
    message: str = Field(min_length=1, max_length=5000)
    tenant_id: str = Field(min_length=1, max_length=100)
