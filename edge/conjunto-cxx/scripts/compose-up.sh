#!/usr/bin/env bash
# Levanta el stack completo y espera a que los servicios estén healthy.
# Uso:
#   ./scripts/compose-up.sh              # levanta todo
#   ./scripts/compose-up.sh core         # levanta perfil core
#   ./scripts/compose-up.sh --timeout 300
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

TIMEOUT=240
PROFILE=""
while [ $# -gt 0 ]; do
    case "$1" in
        --timeout) TIMEOUT="$2"; shift 2 ;;
        core|edge|data|obs|tools) PROFILE="$1"; shift ;;
        *) echo "Flag desconocido: $1"; exit 2 ;;
    esac
done

if [ ! -f .env ]; then
    echo "→ No hay .env; copiando de .env.example…"
    cp .env.example .env
    echo "  Edita .env si quieres cambiar puertos o credenciales."
fi

if [ -n "$PROFILE" ]; then
    echo "→ Levantando servicios con perfil: $PROFILE"
    docker compose --profile "$PROFILE" up -d
else
    echo "→ Levantando stack completo…"
    docker compose up -d
fi

echo "→ Esperando a que los servicios estén healthy (timeout ${TIMEOUT}s)…"

start="$(date +%s)"
while true; do
    now="$(date +%s)"
    elapsed=$((now - start))
    if [ "$elapsed" -ge "$TIMEOUT" ]; then
        echo "✗ Timeout esperando healthy."
        docker compose ps
        exit 1
    fi

    # Cuenta servicios healthy y total.
    total="$(docker compose ps --services 2>/dev/null | wc -l | tr -d ' ')"
    healthy="$(docker compose ps --format json 2>/dev/null | \
        grep -o '"Health":"healthy"' | wc -l | tr -d ' ')"
    running="$(docker compose ps --format json 2>/dev/null | \
        grep -o '"State":"running"' | wc -l | tr -d ' ')"

    printf "\r  %02ds · running %s/%s · healthy %s" "$elapsed" "$running" "$total" "$healthy"

    if [ "$total" -gt 0 ] && [ "$healthy" -ge "$total" ]; then
        echo ""
        echo "✓ Todos los servicios healthy."
        break
    fi
    sleep 3
done

echo ""
docker compose ps
echo ""
echo "Endpoints:"
echo "  API:        http://localhost:${API_PORT:-5000}"
echo "  Swagger:    http://localhost:${API_PORT:-5000}/swagger"
echo "  AI:         http://localhost:${AI_PORT:-8000}/docs"
echo "  Web Admin:  http://localhost:${WEB_ADMIN_PORT:-5173}"
echo "  PB Bridge:  http://localhost:${PB_BRIDGE_PORT:-5100}/swagger"
echo "  Edge:       http://localhost:${EDGE_HEALTH_PORT:-8080}/metrics"
echo "  Grafana:    http://localhost:${GRAFANA_PORT:-3000}"
echo "  Prometheus: http://localhost:${PROMETHEUS_PORT:-9090}"
echo "  RabbitMQ:   http://localhost:${RABBITMQ_MGMT_PORT:-15672}"
echo "  MinIO:      http://localhost:${MINIO_CONSOLE_PORT:-9001}"
