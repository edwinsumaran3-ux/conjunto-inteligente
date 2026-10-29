"""Regresión de seguridad — portada de VigilanciaPlatform (.NET)
tests/security/security-regression.py, adaptada al repositorio Python/React
unificado tras la fusión (ver docs/10-fusion-unificacion-plataforma.md).

Verifica:
  - el dashboard trae las cabeceras CSP mínimas en su index.html
  - no hay manejadores de eventos inline en HTML crudo
  - ningún servicio confía en un X-Tenant-Id que mande el cliente
    (la resolución de tenant es responsabilidad de shared/security/tenant_context.py)
  - todo archivo .json del repo parsea correctamente
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []

html = (ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
for marker in ("Content-Security-Policy", "frame-ancestors 'none'", "script-src 'self'"):
    if marker not in html:
        errors.append(f"dashboard/index.html: falta '{marker}'")
if re.search(r'\bon\w+\s*=\s*"', html, re.I):
    errors.append("dashboard/index.html: manejador de evento inline detectado")

for service_main in ROOT.glob("services/*/src/main.py"):
    text = service_main.read_text(encoding="utf-8")
    if "request.headers[\"x-tenant-id\"]" in text.lower() or "headers.get(\"x-tenant-id\")" in text.lower():
        errors.append(f"{service_main}: confía directamente en X-Tenant-Id del cliente; usar shared/security/tenant_context.py")

skip_dirs = {"node_modules", ".git", "dist", "build"}
for p in ROOT.rglob("*.json"):
    if any(part in skip_dirs for part in p.parts):
        continue
    try:
        json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"invalid-json:{p}:{e}")

print("SECURITY_REGRESSION", "PASS" if not errors else "FAIL")
if errors:
    print("\n".join(errors))
    raise SystemExit(1)
