import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

VALID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        supplied = request.headers.get("x-correlation-id")
        correlation_id = supplied if supplied and VALID.match(supplied) else uuid.uuid4().hex
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-Id"] = correlation_id
        return response
