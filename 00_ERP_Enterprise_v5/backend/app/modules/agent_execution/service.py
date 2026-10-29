from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import hashlib, json

@dataclass(frozen=True)
class ToolPolicy:
    name: str
    risk: str
    requires_human_approval: bool
    enabled: bool = True

@dataclass(frozen=True)
class ExecutionDecision:
    allowed: bool
    status: str
    reason: str
    requires_human_approval: bool

def canonical_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()
    return hashlib.sha256(raw).hexdigest()

def decide(*, policy: ToolPolicy, requested_by: str, approved: bool = False) -> ExecutionDecision:
    if not policy.enabled:
        return ExecutionDecision(False, "rejected", "tool_disabled", policy.requires_human_approval)
    if policy.requires_human_approval and not approved:
        return ExecutionDecision(False, "awaiting_human", "human_approval_required", True)
    if requested_by.strip() == "":
        return ExecutionDecision(False, "rejected", "actor_required", policy.requires_human_approval)
    return ExecutionDecision(True, "accepted", "policy_allowed", policy.requires_human_approval)
