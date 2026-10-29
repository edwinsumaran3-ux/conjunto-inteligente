#!/usr/bin/env bash
# E2E en navegador REAL (Chromium+WebGL) del Centro de Mando BIM: migra, crea tenant, arranca la API sirviendo /bim, siembra el gemelo por API y ejecuta frontend/e2e/viewer.e2e.mjs.
# Requiere: PHASE13_DATABASE_URL (propietario), frontend compilado (npm run build:bim), puppeteer-core + Chromium (CHROME_PATH) o E2E_NODE_PATH con @sparticuz/chromium.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}; OWNER=${PHASE13_DATABASE_URL//+asyncpg/}; PORT=${E2E_PORT:-8140}
export MIGRATION_DATABASE_URL=$PHASE13_DATABASE_URL APP_DB_PASSWORD=${APP_DB_PASSWORD:-browser-e2e-password-123} PYTHONPATH=.
"$PY" scripts/apply_sql_migrations.py >/dev/null
OUT=$(BOOTSTRAP_DATABASE_URL=$OWNER "$PY" scripts/bootstrap_tenant.py --name "E2E $RANDOM" --email "e2e$RANDOM@visor.co" --password "Clave-segura-123")
TID=$(echo "$OUT" | sed -n 's/^tenant_id=//p'); EMAIL=$(echo "$OUT" | sed -n 's/^admin=//p')
APPURL=${PHASE13_DATABASE_URL/\/\/*@/\/\/erp_app:$APP_DB_PASSWORD@}; SECRET=$("$PY" -c "print('k'*48)")
DATABASE_URL=$APPURL JWT_SECRET_KEY=$SECRET BIM_STATIC_DIR=$PWD/frontend/dist/bim "$PY" -m uvicorn backend.app.main:app --port "$PORT" --log-level warning & SRV=$!
trap 'kill $SRV 2>/dev/null || true' EXIT
for i in $(seq 1 60); do curl -sf "http://127.0.0.1:$PORT/healthz" >/dev/null && break; sleep 0.5; done
"$PY" scripts/seed_demo_twin.py --base "http://127.0.0.1:$PORT" --tenant "$TID" --email "$EMAIL" --password "Clave-segura-123" >/dev/null
E2E_BASE="http://127.0.0.1:$PORT" E2E_TENANT=$TID E2E_EMAIL=$EMAIL E2E_PWD="Clave-segura-123" E2E_OUT=${E2E_OUT:-frontend/e2e-out} node frontend/e2e/viewer.e2e.mjs
