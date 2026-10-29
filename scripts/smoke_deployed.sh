#!/usr/bin/env bash
# Prueba de humo contra un despliegue real. Uso:
#   API_URL=https://xxx.up.railway.app WEB_URL=https://xxx.vercel.app ./scripts/smoke_deployed.sh
set -uo pipefail
: "${API_URL:?Define API_URL (https://...up.railway.app)}"
: "${WEB_URL:?Define WEB_URL (https://...vercel.app)}"
fail=0
check() { # nombre esperado obtenido
  if [[ "$3" == "$2" ]]; then echo "OK    $1 ($3)"; else echo "FALLA $1: esperado $2, obtenido $3"; fail=1; fi
}
code() { curl -sS -o /dev/null -m 20 -w '%{http_code}' "$@" 2>/dev/null || true; }
check "API /health"                 200 "$(code "$API_URL/health")"
check "API /ready (BD conectada)"   200 "$(code "$API_URL/ready")"
check "API /api/auth/me sin token"  401 "$(code "$API_URL/api/auth/me")"
check "API /api/residents sin token" 401 "$(code "$API_URL/api/residents")"
check "API Swagger oculto en prod"  404 "$(code "$API_URL/swagger/index.html")"
# CORS: el origen del frontend debe estar permitido y uno ajeno no.
allow=$(curl -sS -m 20 -D - -o /dev/null -X OPTIONS "$API_URL/api/auth/me" -H "Origin: $WEB_URL" -H "Access-Control-Request-Method: GET" -H "Access-Control-Request-Headers: authorization" 2>/dev/null | tr -d '\r' | awk -F': ' 'tolower($1)=="access-control-allow-origin"{print $2}')
check "CORS origen del frontend" "$WEB_URL" "${allow:-ninguno}"
evil=$(curl -sS -m 20 -D - -o /dev/null -X OPTIONS "$API_URL/api/auth/me" -H "Origin: https://evil.example" -H "Access-Control-Request-Method: GET" 2>/dev/null | tr -d '\r' | awk -F': ' 'tolower($1)=="access-control-allow-origin"{print $2}')
check "CORS origen ajeno bloqueado" "ninguno" "${evil:-ninguno}"
# Frontend
check "WEB /"                       200 "$(code "$WEB_URL/")"
check "WEB ruta SPA /ordenes"       200 "$(code "$WEB_URL/ordenes")"
hsts=$(curl -sS -m 20 -D - -o /dev/null "$WEB_URL/" | tr -d '\r' | grep -ci '^strict-transport-security')
check "WEB cabecera HSTS" 1 "$hsts"
exit $fail
