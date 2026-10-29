from __future__ import annotations
import re
from typing import Any


class ResponseGuard:
    SECRET_PATTERNS = [
        re.compile(
            r"(?i)(api[_ -]?key|secret|password|authorization)\s*[:=]\s*[^\s,;]+"
        )
    ]
    ACTION_WORDS = {
        "purchase",
        "approve_purchase",
        "delete",
        "disable",
        "shutdown",
        "transfer_money",
        "send_payment",
    }

    def sanitize(self, text: str) -> str:
        value = text.strip()
        for pattern in self.SECRET_PATTERNS:
            value = pattern.sub(lambda m: m.group(1) + "=[REDACTED]", value)
        return value

    def validate(self, result: dict[str, Any]) -> tuple[bool, list[str]]:
        warnings: list[str] = []
        text = result.get("text")
        if not isinstance(text, str) or not text.strip():
            return False, ["empty_model_output"]
        lower = text.lower()
        proposed = [word for word in self.ACTION_WORDS if word in lower]
        if proposed:
            warnings.append("critical_action_language_detected")
        return True, warnings
