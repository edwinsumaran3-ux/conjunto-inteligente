from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolDecision:
    allowed: bool
    reason: str


class ToolPolicy:
    READ_ONLY = {"get_asset_history", "get_area_by_keywords"}
    HUMAN_APPROVAL = {
        "create_purchase",
        "approve_purchase",
        "close_incident",
        "send_notification",
    }

    def decide(
        self, *, tool: str, actor: str = "llm", approved: bool = False
    ) -> ToolDecision:
        if tool in self.READ_ONLY:
            return ToolDecision(True, "read_only_tool")
        if tool in self.HUMAN_APPROVAL:
            if actor != "human" or not approved:
                return ToolDecision(False, "human_approval_required")
            return ToolDecision(True, "explicit_human_approval")
        return ToolDecision(False, "tool_not_allowlisted")

    def authorize_payload(self, tool: str, payload: dict[str, Any]) -> ToolDecision:
        if tool not in self.READ_ONLY and tool not in self.HUMAN_APPROVAL:
            return ToolDecision(False, "tool_not_allowlisted")
        return ToolDecision(True, "schema_gate_pending")
