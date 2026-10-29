import hmac
import os
from fastapi import Header, HTTPException


def require_operator(x_operator_token: str | None = Header(default=None)) -> str:
    expected = os.getenv('OPERATOR_TOKEN', '')
    if not expected:
        raise HTTPException(503, 'operator authorization is not configured')
    if not x_operator_token or not hmac.compare_digest(x_operator_token, expected):
        raise HTTPException(401, 'operator authorization required')
    return 'operator'


def read_guard(x_operator_token: str | None = Header(default=None)) -> str:
    """Protege los GET sensibles (aprobaciones, journal, registro de equipo) cuando REQUIRE_AUTH_FOR_READS=true.

    Por defecto está desactivado para no romper el dashboard actual, que consulta sin token.
    En producción debe activarse (y el dashboard enviar X-Operator-Token).
    """
    if os.getenv('REQUIRE_AUTH_FOR_READS', 'false').lower() not in ('1', 'true', 'yes'):
        return 'anonymous'
    return require_operator(x_operator_token)
