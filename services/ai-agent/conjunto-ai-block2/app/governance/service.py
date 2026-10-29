from __future__ import annotations
import hashlib
import json
from typing import Any
from uuid import UUID
from app.core.tool_policy import ToolPolicy
from app.governance.contracts import AgentExecution
from app.governance.registry import get_contract, authorize_tool


class AgentGovernance:
    """Fail-closed execution gate. Tool access is scoped by agent, then by global policy."""

    def __init__(self, tool_policy: ToolPolicy | None = None) -> None:
        self.tool_policy = tool_policy or ToolPolicy()

    def start(
        self,
        *,
        request_id: UUID,
        trace_id: UUID | None,
        tenant_id: str,
        agent: str,
        action: str,
        payload: dict[str, Any],
    ) -> AgentExecution:
        contract = get_contract(agent)
        if len(payload) > contract.max_context_items:
            raise ValueError("agent context item limit exceeded")
        normalized = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), default=str
        ).encode()
        return AgentExecution(
            request_id=request_id,
            trace_id=trace_id,
            tenant_id=tenant_id,
            agent=contract.name,
            action=action,
            input_hash=hashlib.sha256(normalized).hexdigest(),
            status="awaiting_human"
            if action in contract.human_required_actions
            else "accepted",
            requires_human_review=action in contract.human_required_actions,
            policy_reason="Agent-specific contract + global tool policy evaluated; consequential actions remain human-gated.",
        )

    def authorize_tool(
        self,
        *,
        agent: str,
        tool: str,
        actor: str = "llm",
        approved: bool = False,
        write: bool = False,
    ):
        if not authorize_tool(agent, tool, write):
            from app.core.tool_policy import ToolDecision

            return ToolDecision(False, "agent_tool_not_allowlisted")
        return self.tool_policy.decide(tool=tool, actor=actor, approved=approved)
