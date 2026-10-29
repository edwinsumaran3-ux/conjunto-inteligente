from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Copia local (propiedad de este servicio) del middleware de cabeceras de
# seguridad definido en shared/security/security_headers_middleware.py.
# Se duplica en vez de importarse entre contenedores porque cada servicio
# construye su imagen con un contexto Docker aislado a su propia carpeta;
# el contrato canónico y su justificación viven en shared/security/.
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
