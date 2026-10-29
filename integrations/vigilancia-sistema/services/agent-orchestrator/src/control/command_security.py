from __future__ import annotations
import hashlib, hmac, json, os
from typing import Any


def _keys() -> dict[str, bytes]:
    raw = os.getenv('EQUIPMENT_HMAC_KEYS_JSON', '{}')
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return {str(k): str(v).encode('utf-8') for k, v in data.items() if v}


def canonical_command(command: Any) -> bytes:
    payload = {
        'command_id': command.command_id,
        'nonce': command.nonce,
        'equipment_type': command.equipment_type.value,
        'equipment_id': command.equipment_id,
        'action': command.action,
        'parameters': command.parameters,
        'issued_at': command.issued_at,
        'expires_at': command.expires_at,
        'issued_by': command.issued_by,
    }
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def sign_command(command: Any, secret: str) -> str:
    return hmac.new(secret.encode(), canonical_command(command), hashlib.sha256).hexdigest()


def verify_command(command: Any) -> bool:
    secret = _keys().get(command.equipment_id)
    if not secret or not command.signature:
        return False
    expected = hmac.new(secret, canonical_command(command), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, command.signature)


def sign_for_equipment(command: Any) -> str:
    """Firma el comando con la clave HMAC propia del equipo destino (EQUIPMENT_HMAC_KEYS_JSON).

    Devuelve '' si no hay clave provisionada para ese equipo: el registro lo rechazará
    (fail-closed) en lugar de enviarse con una firma estática que nunca verificaría.
    """
    secret = _keys().get(command.equipment_id)
    if not secret:
        return ''
    return hmac.new(secret, canonical_command(command), hashlib.sha256).hexdigest()
