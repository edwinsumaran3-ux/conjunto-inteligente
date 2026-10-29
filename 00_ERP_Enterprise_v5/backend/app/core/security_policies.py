"""Input policies shared by authentication endpoints."""
import re
from email.utils import parseaddr

class SecurityPolicyViolation(ValueError):
    pass

def validate_login_identifier(value: str) -> str:
    if not isinstance(value, str):
        raise SecurityPolicyViolation("login identifier must be text")
    value = value.strip().casefold()
    if len(value) > 254 or not value or any(ord(ch) < 32 for ch in value):
        raise SecurityPolicyViolation("invalid login identifier")
    parsed = parseaddr(value)[1]
    if parsed != value or "@" not in value:
        raise SecurityPolicyViolation("login identifier must be an email address")
    local, domain = value.rsplit("@", 1)
    if not local or not domain or "." not in domain or re.search(r"\s", value):
        raise SecurityPolicyViolation("invalid email address")
    return value
