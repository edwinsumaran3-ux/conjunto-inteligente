from dataclasses import dataclass
from decimal import Decimal
from app.core.config import get_settings


@dataclass(frozen=True)
class PolicyDecision:
    action: str
    requires_human_review: bool
    requires_multi_quote: bool
    reason: str


class PolicyEngine:
    def __init__(
        self,
        auto_approve_limit: Decimal | None = None,
        multi_quote_limit: Decimal | None = None,
    ) -> None:
        settings = get_settings()
        self.auto_approve_limit = (
            auto_approve_limit
            if auto_approve_limit is not None
            else Decimal(settings.auto_approve_limit_cop)
        )
        self.multi_quote_limit = (
            multi_quote_limit
            if multi_quote_limit is not None
            else Decimal(settings.multi_quote_limit_cop)
        )

    def evaluate(
        self, amount_cop: Decimal, urgency: str = "normal", severity: str = "normal"
    ) -> PolicyDecision:
        if amount_cop < 0:
            raise ValueError("amount_cop cannot be negative")
        if severity in {"high", "critical"}:
            return PolicyDecision(
                "human_approval",
                True,
                amount_cop >= self.multi_quote_limit,
                "High or critical severity requires human approval.",
            )
        if urgency == "emergency":
            return PolicyDecision(
                "human_approval",
                True,
                amount_cop >= self.multi_quote_limit,
                "Emergency procurement requires human review and justification.",
            )
        if amount_cop <= self.auto_approve_limit:
            return PolicyDecision(
                "auto_approve_eligible",
                False,
                False,
                "Amount is within the configured automatic approval threshold.",
            )
        if amount_cop >= self.multi_quote_limit:
            return PolicyDecision(
                "multi_quote_review",
                True,
                True,
                "Amount meets the configured multi-quote threshold.",
            )
        return PolicyDecision(
            "review",
            True,
            False,
            "Amount exceeds the configured automatic approval threshold.",
        )
