from __future__ import annotations
import hashlib, hmac, json
from datetime import datetime, timezone
from typing import Any

ALLOWED_COMMANDS={"set_output","set_relay","set_light","lock","unlock","start_pump","stop_pump","start_drone_mission","stop_drone_mission","safe_state"}
SAFETY_STATES={"armed","safe","kill_switch","quarantined"}

def canonical_json(value: Any)->str:
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,default=str)

def sha256_json(value: Any)->str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()

def sign_envelope(envelope: dict[str,Any], secret: bytes)->str:
    return hmac.new(secret,canonical_json(envelope).encode(),hashlib.sha256).hexdigest()

def verify_signature(envelope: dict[str,Any], signature: str, secret: bytes)->bool:
    return hmac.compare_digest(sign_envelope(envelope,secret),signature)

def key_fingerprint(secret: bytes)->str:
    return hashlib.sha256(secret).hexdigest()

def command_allowed(command_type: str, capabilities: list[str])->bool:
    return command_type in ALLOWED_COMMANDS and command_type in capabilities

def safety_allows(state: str, command_type: str)->bool:
    if state not in SAFETY_STATES: return False
    if state in {"kill_switch","quarantined"}: return command_type=="safe_state"
    if state=="safe": return command_type in {"safe_state","stop_pump","stop_drone_mission","lock"}
    return True

def is_expired(expires_at: datetime, now: datetime|None=None)->bool:
    now=now or datetime.now(timezone.utc)
    return expires_at.astimezone(timezone.utc)<=now
