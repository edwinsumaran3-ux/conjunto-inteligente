#!/usr/bin/env bash
# Ejecuta gate real (PostgreSQL 16 + Redis) y pytest SIN Docker.
# Requiere: binarios instalados con vendor/install_offline.sh, y un venv con requirements.lock + pytest + openpyxl + pytest-asyncio.
set -euo pipefail
cd "$(dirname "$0")/.."
PGBIN=/usr/lib/postgresql/16/bin; PBIN=$PGBIN; WORK=$(mktemp -d); PORT_PG=${PORT_PG:-55432}; PORT_RD=${PORT_RD:-56379}
PY=${PYTHON:-python3}
RUN_AS=(); if [[ $EUID -eq 0 ]]; then chown postgres "$WORK"; RUN_AS=(su postgres -c); fi
pgrun() { if [[ ${#RUN_AS[@]} -gt 0 ]]; then "${RUN_AS[@]}" "$*"; else bash -c "$*"; fi; }
cleanup() { pgrun "$PGBIN/pg_ctl -D $WORK/data stop -m fast" >/dev/null 2>&1 || true; redis-cli -p $PORT_RD shutdown nosave >/dev/null 2>&1 || true; rm -rf "$WORK"; }
trap cleanup EXIT
pgrun "$PGBIN/initdb -D $WORK/data -U erp --auth=trust >/dev/null"
pgrun "$PGBIN/pg_ctl -D $WORK/data -o '-p $PORT_PG -c max_connections=200 -c wal_level=replica -c unix_socket_directories=$WORK' -l $WORK/pg.log -w start >/dev/null"
"$PGBIN/psql" -h "$WORK" -p $PORT_PG -U erp -d postgres -qc "CREATE DATABASE erp_test"
redis-server --daemonize yes --port $PORT_RD --save "" --dir "$WORK" >/dev/null
export PHASE13_DATABASE_URL="postgresql+asyncpg://erp@127.0.0.1:$PORT_PG/erp_test" PHASE13_REDIS_URL="redis://127.0.0.1:$PORT_RD/0" PYTHONPATH=.
"$PY" scripts/phase13_real_infra_gate.py
# aplica TODAS las migraciones en una base limpia y valida cada SQL del backend contra ese esquema
"$PBIN/psql" -h "$WORK" -p $PORT_PG -U erp -d postgres -qc "CREATE DATABASE sqlval"
for m in backend/app/modules/digital_twin/migrations/001_outbox_events.sql migrations/sql/2026*.sql; do "$PBIN/psql" -h "$WORK" -p $PORT_PG -U erp -d sqlval -q -v ON_ERROR_STOP=1 -f "$m" >/dev/null 2>&1 || { echo "MIGRACION FALLIDA: $m"; exit 1; }; done
PHASE13_DATABASE_URL="postgresql://erp@127.0.0.1:$PORT_PG/sqlval" "$PY" tools/validate_sql_schema.py
# Alembic debe producir el MISMO esquema que los .sql directos (+ alembic_version)
"$PBIN/psql" -h "$WORK" -p $PORT_PG -U erp -d postgres -qc "CREATE DATABASE alem"
DATABASE_URL="postgresql+asyncpg://erp@127.0.0.1:$PORT_PG/alem" "$PY" -m alembic upgrade head >/dev/null
A=$("$PBIN/psql" -h "$WORK" -p $PORT_PG -U erp -d alem -Atc "select count(*) from pg_tables where schemaname='public' and tablename<>'alembic_version'"); B=$("$PBIN/psql" -h "$WORK" -p $PORT_PG -U erp -d sqlval -Atc "select count(*) from pg_tables where schemaname='public'")
[[ "$A" == "$B" ]] && echo "ALEMBIC_OK tablas=$A" || { echo "ALEMBIC_DIFERENTE alembic=$A sql=$B"; exit 1; }
"$PY" -m pytest -q
