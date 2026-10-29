from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict


class AIRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID = Field(default_factory=uuid4)
    trace_id: UUID | None = None


class AIResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    status: str
    agent: str
    confidence: float = Field(ge=0.0, le=1.0)
    requires_human_review: bool
    data_source_status: str
    result: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
