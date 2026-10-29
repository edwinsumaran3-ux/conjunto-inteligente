import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

VALID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

# Portado de CorrelationIdMiddleware.cs: si el llamador manda un
# X-Correlation-Id válido se conserva (permite trazar una petición del
# dashboard a través de ingestion -> rabbit -> correlation-engine -> agentes);
# si no, se genera uno nuevo. Nunca se confía en un id con formato inválido.
class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        supplied = request.headers.get("x-correlation-id")
        correlation_id = supplied if supplied and VALID.match(supplied) else uuid.uuid4().hex
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-Id"] = correlation_id
        return response
