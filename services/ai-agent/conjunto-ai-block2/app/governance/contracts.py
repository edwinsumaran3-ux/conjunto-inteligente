from __future__ import annotations
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field


class AgentName(StrEnum):
    RECEPTION = "reception"
    DIAGNOSTIC = "diagnostic"
    PROCUREMENT = "procurement"
    PLAN = "plan"
    MAINTENANCE = "maintenance"
    VENDOR = "vendor"
    INVENTORY = "inventory"
    FINANCE = "finance"
    SECURITY = "security"
    COMMUNICATION = "communication"
    REPORTING = "reporting"
    COMPLIANCE = "compliance"
    SURVEILLANCE_ADVISOR = "surveillance_advisor"


class MemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    memory_id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(min_length=1)
    agent: AgentName
    source: str = Field(min_length=1, max_length=500)
    content: dict[str, Any]
    confidence: float = Field(ge=0, le=1)
    version: int = Field(ge=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None


class AgentExecution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    execution_id: UUID = Field(default_factory=uuid4)
    request_id: UUID
    trace_id: UUID | None = None
    tenant_id: str = Field(min_length=1)
    agent: AgentName
    action: str = Field(min_length=1, max_length=200)
    input_hash: str = Field(min_length=64, max_length=64)
    status: str = Field(pattern="^(accepted|completed|rejected|failed|awaiting_human)$")
    requires_human_review: bool
    policy_reason: str = Field(min_length=1, max_length=1000)
    tool_calls: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
