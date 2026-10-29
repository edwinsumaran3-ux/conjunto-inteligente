from decimal import Decimal
from pydantic import Field
from .common import AIRequest


class ProcurementRequest(AIRequest):
    tenant_id: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=5000)
    amount_cop: Decimal = Field(gt=0)
    urgency: str = Field(default="normal", pattern="^(normal|urgent|emergency)$")
    severity: str = Field(default="normal", pattern="^(normal|high|critical)$")
