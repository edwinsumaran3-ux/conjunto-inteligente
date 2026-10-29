from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Portado de VigilanciaPlatform (.NET) SecurityHeadersMiddleware.cs — mismas
# cabeceras, misma política, aplicadas aquí a cada respuesta de un servicio
# FastAPI en lugar de un pipeline ASP.NET. Un solo propósito: no mezclar con
# CorrelationIdMiddleware aunque ambos se registren juntos en main.py.
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    CSP = (
        "default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; "
        "form-action 'self'; img-src 'self' data: blob:; media-src 'self' blob:; "
        "style-src 'self'; script-src 'self'; connect-src 'self' https: wss:;"
    )

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = self.CSP
        return response
