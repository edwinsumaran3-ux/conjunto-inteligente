#!/usr/bin/env bash
# Prueba REAL del cliente del visor contra el API (PostgreSQL ya migrado como PHASE13_DATABASE_URL propietario + rol erp_app).
# Requiere: PHASE13_DATABASE_URL (propietario), APP_DB_PASSWORD, y dependencias de frontend instaladas. Arranca uvicorn temporal en :8123.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}; OWNER=${PHASE13_DATABASE_URL//+asyncpg/}
export MIGRATION_DATABASE_URL=$PHASE13_DATABASE_URL APP_DB_PASSWORD=${APP_DB_PASSWORD:-viewer-it-password-1234} PYTHONPATH=.
"$PY" scripts/apply_sql_migrations.py >/dev/null
OUT=$(BOOTSTRAP_DATABASE_URL=$OWNER "$PY" scripts/bootstrap_tenant.py --name "Visor IT $RANDOM" --email "it$RANDOM@visor.co" --password "Clave-segura-123")
TID=$(echo "$OUT" | sed -n 's/^tenant_id=//p'); EMAIL=$(echo "$OUT" | sed -n 's/^admin=//p')
APPURL=${PHASE13_DATABASE_URL/\/\/*@/\/\/erp_app:$APP_DB_PASSWORD@}
DATABASE_URL=$APPURL JWT_SECRET_KEY=$(printf 'k%.0s' {1..48}) "$PY" -m uvicorn backend.app.main:app --port 8123 --log-level warning & SRV=$!
trap 'kill $SRV 2>/dev/null || true' EXIT
for i in $(seq 1 40); do curl -sf http://127.0.0.1:8123/healthz >/dev/null && break; sleep 0.5; done
cd frontend && BIM_API_URL=http://127.0.0.1:8123 BIM_TENANT=$TID BIM_EMAIL=$EMAIL BIM_PWD=Clave-segura-123 npx vitest run bim/src/api.integration.test.ts
