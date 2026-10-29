#!/usr/bin/env python3
"""Genera un OpenAPI 3.0 (esqueleto de rutas) a partir de los controladores .NET.

Es un contrato DERIVADO del código fuente (rutas, verbos, parámetros de ruta), no el que emite Swashbuckle.
Los esquemas de cuerpo/respuesta son genéricos. Sustituir por el swagger.json real del build:
    dotnet swagger tofile --output openapi/conjunto-api.json <Api.dll> v1
"""
import json, re, sys
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "ConjuntoInteligente/src/Api/ConjuntoInteligente.Api/Controllers"
out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "apps/web-admin/frontend/web-admin/openapi/conjunto-api.yaml"
paths: dict[str, dict[str, dict]] = {}
for f in sorted(root.glob("*.cs")):
    src = f.read_text(encoding="utf8")
    m = re.search(r'\[Route\("([^"]*)"\)\]', src)
    base = m.group(1) if m else ""
    class_auth = bool(re.search(r"\[Authorize[^\]]*\]\s*(?:\[[^\]]*\]\s*)*(?:public\s+)?(?:sealed\s+)?(?:partial\s+)?class", src))
    for am in re.finditer(r'((?:\s*\[[^\]]+\]\s*)+)(?:public\s+)(?:async\s+)?[\w<>\[\]?., ]+\s+(\w+)\s*\(', src):
        attrs, name = am.group(1), am.group(2)
        hm = re.search(r'\[Http(Get|Post|Put|Delete|Patch)(?:\("([^"]*)"\))?\]', attrs)
        if not hm:
            continue
        verb, sub = hm.group(1).lower(), hm.group(2) or ""
        raw = "/".join(x for x in (base.strip("/"), sub.strip("/")) if x)
        url = "/" + re.sub(r"\{(\w+)(?::\w+)?\}", r"{\1}", raw)
        params = re.findall(r"\{(\w+)\}", url)
        op = {"operationId": f"{f.stem}_{name}", "tags": [f.stem.replace("Controller", "")],
              "responses": {"200": {"description": "OK"}, "401": {"description": "No autenticado"}, "403": {"description": "Sin permiso"}}}
        if params:
            op["parameters"] = [{"name": p, "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}} for p in params]
        if verb in ("post", "put", "patch"):
            op["requestBody"] = {"content": {"application/json": {"schema": {"type": "object"}}}}
            op["responses"]["201"] = {"description": "Creado"}
        if "AllowAnonymous" in attrs:
            op["security"] = []
        paths.setdefault(url, {})[verb] = op

doc = {"openapi": "3.0.3",
       "info": {"title": "Conjunto Inteligente API", "version": "v1", "description": "Contrato derivado de los controladores (esqueleto). Regenerar con swagger real en CI."},
       "servers": [{"url": "https://TU-API.up.railway.app"}],
       "components": {"securitySchemes": {"bearer": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}}},
       "security": [{"bearer": []}],
       "paths": dict(sorted(paths.items()))}
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf8")  # JSON es YAML válido
print(f"{sum(len(v) for v in paths.values())} operaciones en {len(paths)} rutas -> {out}")
