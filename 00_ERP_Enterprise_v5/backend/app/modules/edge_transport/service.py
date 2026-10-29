from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()


def transport_message(envelope: dict[str, Any]) -> bytes:
    """Canonical bytes signed by the edge gateway."""
    return canonical(envelope)


def decode_signature(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except Exception as exc:  # pragma: no cover - defensive boundary
        raise ValueError("INVALID_SIGNATURE_ENCODING") from exc


def decode_public_key(value: str):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    raw = value.strip()
    if raw.startswith("-----BEGIN"):
        return serialization.load_pem_public_key(raw.encode())
    try:
        data = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise ValueError("INVALID_PUBLIC_KEY_ENCODING") from exc
    if len(data) != 32:
        raise ValueError("INVALID_ED25519_PUBLIC_KEY_LENGTH")
    return Ed25519PublicKey.from_public_bytes(data)


def verify_ed25519(envelope: dict[str, Any], signature_b64: str, public_key: str) -> bool:
    from cryptography.exceptions import InvalidSignature

    try:
        key = decode_public_key(public_key)
        key.verify(decode_signature(signature_b64), transport_message(envelope))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def payload_hash(payload: Any) -> str:
    return hashlib.sha256(canonical(payload)).hexdigest()


def constant_time_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
