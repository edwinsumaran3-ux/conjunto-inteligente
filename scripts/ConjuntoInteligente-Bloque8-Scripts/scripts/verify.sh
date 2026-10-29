#!/usr/bin/env bash
set +e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; source "$SCRIPT_DIR/lib/common.sh"
PASS=0; FAIL=0; RESULTS=()
check(){ local name="$1" req="$2" cmd="$3" min="$4" out ver; out="$(bash -c "$cmd" 2>/dev/null)"; ver="$(extract_version "$out")"; if [ -z "$out" ] || [ -z "$ver" ]; then RESULTS+=("$(printf '%-14s | %-30s | FAIL (no instalado)' "$name" "$req")"); FAIL=$((FAIL+1)); return; fi; if [ -n "$min" ] && ! version_ge "$ver" "$min"; then RESULTS+=("$(printf '%-14s | %-30s | FAIL (%s < %s)' "$name" "$req" "$ver" "$min")"); FAIL=$((FAIL+1)); return; fi; RESULTS+=("$(printf '%-14s | %-30s | PASS (%s)' "$name" "$req" "$ver")"); PASS=$((PASS+1)); }
check dotnet '>= 8.0.100' 'dotnet --version' 8.0.100
check python '>= 3.12.0' 'python3.12 --version' 3.12.0
check pip '>= 23.0' 'python3.12 -m pip --version' 23.0
check poetry '>= 1.8.0' 'poetry --version' 1.8.0
check node '>= 20.0.0' 'node --version' 20.0.0
check pnpm '>= 9.0.0' 'pnpm --version' 9.0.0
check cmake '>= 3.28.0' 'cmake --version' 3.28.0
check ninja '>= 1.11.0' 'ninja --version' 1.11.0
check gcc '>= 11.0.0' 'gcc --version' 11.0.0
check pio '>= 6.1.0' 'pio --version' 6.1.0
check terraform '>= 1.7.0' 'terraform version' 1.7.0
check buf '>= 1.30.0' 'buf --version' 1.30.0
check git '>= 2.30.0' 'git --version' 2.30.0
check curl any 'curl --version' ''
if command_exists docker; then if docker info >/dev/null 2>&1; then RESULTS+=("$(printf '%-14s | %-30s | PASS (%s)' docker 'daemon corriendo' "$(extract_version "$(docker --version)")")"); PASS=$((PASS+1)); else RESULTS+=("$(printf '%-14s | %-30s | WARN (daemon no corre)' docker 'daemon corriendo')"); fi; else RESULTS+=("$(printf '%-14s | %-30s | FAIL (no instalado)' docker 'daemon corriendo')"); FAIL=$((FAIL+1)); fi
if command_exists docker && docker compose version >/dev/null 2>&1; then RESULTS+=("$(printf '%-14s | %-30s | PASS (%s)' compose 'Docker Compose v2' "$(docker compose version --short 2>/dev/null)")"); PASS=$((PASS+1)); else RESULTS+=("$(printf '%-14s | %-30s | FAIL (no disponible)' compose 'Docker Compose v2')"); FAIL=$((FAIL+1)); fi
if has_header MQTTClient.h; then RESULTS+=("$(printf '%-14s | %-30s | PASS' paho-mqtt 'MQTTClient.h')"); else RESULTS+=("$(printf '%-14s | %-30s | WARN (opcional)' paho-mqtt 'MQTTClient.h')"); fi
if pkg_config_exists && pkg-config --exists sqlite3 2>/dev/null; then RESULTS+=("$(printf '%-14s | %-30s | PASS (%s)' sqlite3 'dev + pkg-config' "$(pkg-config --modversion sqlite3)")"); PASS=$((PASS+1)); else RESULTS+=("$(printf '%-14s | %-30s | FAIL' sqlite3 'dev + pkg-config')"); FAIL=$((FAIL+1)); fi
echo; echo 'Conjunto Inteligente · Verificación del host'; printf '%-14s | %-30s | %s\n' Herramienta Requisito Resultado; printf '%s\n' '──────────────────────────────────────────────────────────────────────'; printf '%s\n' "${RESULTS[@]}"; printf '%s\n' '──────────────────────────────────────────────────────────────────────'; echo "PASS: $PASS   FAIL: $FAIL"; [ "$FAIL" -eq 0 ] && { echo 'Entorno listo.'; exit 0; }; echo "Hay $FAIL herramienta(s) que no cumplen."; exit 1
