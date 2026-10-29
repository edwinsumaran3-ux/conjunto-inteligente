#!/usr/bin/env bash
# Verificación honesta de la distribución recuperada. Omite solo herramientas/infraestructura ausentes.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 2
mkdir -p docs
STAMP="$(date +%Y-%m-%d_%H%M%S)"
OUT="docs/VERIFICACION_${STAMP}.md"
FAIL=0
printf '# Verificación técnica %s\n\n' "$(date '+%Y-%m-%d %H:%M:%S')" > "$OUT"
printf '| Comprobación | Resultado |\n|---|---|\n' >> "$OUT"
run_step() {
  local name="$1" dir="$2"; shift 2
  local log
  log="$(mktemp)"
  if (cd "$dir" && "$@") >"$log" 2>&1; then
    printf '| %s | ✅ OK |\n' "$name" | tee -a "$OUT"
  else
    local rc=$?
    printf '| %s | ❌ FALLÓ (código %s) |\n' "$name" "$rc" | tee -a "$OUT"
    { printf '\n### %s\n\n```text\n' "$name"; tail -80 "$log"; printf '\n```\n'; } >> "$OUT"
    FAIL=1
  fi
  rm -f "$log"
}
skip_step() { printf '| %s | ⏭️ OMITIDO: %s |\n' "$1" "$2" | tee -a "$OUT"; }
# Static audit must not fail merely because docs/ was absent.
if command -v python3 >/dev/null 2>&1; then
  run_step 'Auditoría estática Python/imports/migraciones' . python3 scripts/auditoria_estatica.py
else skip_step 'Auditoría estática' 'python3 no instalado'; fi
# Main Python ERP suite: use the actual package root and the fixed pytest import mode.
if [[ -f 00_ERP_Enterprise_v5/pytest.ini ]]; then
  run_step 'Pruebas backend ERP (módulos)' 00_ERP_Enterprise_v5 env PYTHONPATH=backend python3 -m pytest -q --import-mode=importlib backend/app/modules
else skip_step 'Pruebas backend ERP' 'no existe 00_ERP_Enterprise_v5/pytest.ini'; fi
if [[ -d services/ai-agent/conjunto-ai-block2/tests ]]; then
  run_step 'Pruebas agentes IA' services/ai-agent/conjunto-ai-block2 python3 -m pytest -q
else skip_step 'Pruebas agentes IA' 'suite no encontrada'; fi
if [[ -f integrations/vigilancia-sistema/scripts/verify_platform.py ]]; then
  run_step 'Vigilancia: verificación de esquema y sintaxis' . python3 integrations/vigilancia-sistema/scripts/verify_platform.py
  run_step 'Vigilancia: pruebas de integración/unidad' integrations/vigilancia-sistema python3 -m pytest -q tests
  run_step 'Vigilancia: pruebas del orquestador de agentes' integrations/vigilancia-sistema python3 -m pytest -q services/agent-orchestrator/tests
else skip_step 'Vigilancia' 'módulo no encontrado'; fi
if [[ -f 00_ERP_Enterprise_v5/frontend/package.json ]]; then
  if command -v pnpm >/dev/null 2>&1; then
    run_step 'Frontend ERP: instalación reproducible' 00_ERP_Enterprise_v5/frontend pnpm install --frozen-lockfile
    run_step 'Frontend ERP: typecheck y build' 00_ERP_Enterprise_v5/frontend pnpm run build
  elif command -v npm >/dev/null 2>&1 && [[ -d 00_ERP_Enterprise_v5/frontend/node_modules ]]; then
    run_step 'Frontend ERP: typecheck y build' 00_ERP_Enterprise_v5/frontend npm run build
  else skip_step 'Frontend ERP build' 'faltan pnpm o node_modules; no se puede validar sin instalar dependencias'; fi
else skip_step 'Frontend ERP build' 'package.json no encontrado'; fi
if command -v dotnet >/dev/null 2>&1; then
  if [[ -f ConjuntoInteligente/ConjuntoInteligente.sln ]]; then
    run_step '.NET build' ConjuntoInteligente dotnet build ConjuntoInteligente.sln --warnaserror
    run_step '.NET tests' ConjuntoInteligente dotnet test ConjuntoInteligente.sln --no-build
  else skip_step '.NET build/tests' 'la solución .NET no está en esta distribución recuperada'; fi
else skip_step '.NET build/tests' 'SDK dotnet no instalado'; fi
if [[ -n "${DATABASE_URL:-}" ]]; then
  if command -v psql >/dev/null 2>&1; then
    skip_step 'Pruebas PostgreSQL/RLS' 'hay DATABASE_URL, pero la prueba destructiva histórica no se ejecuta automáticamente; requiere un entorno de CI aislado'
  else skip_step 'Pruebas PostgreSQL/RLS' 'DATABASE_URL definido pero psql no instalado'; fi
else skip_step 'Pruebas PostgreSQL/RLS' 'DATABASE_URL no definido'; fi
if [[ -n "${API_URL:-}" ]]; then
  run_step 'Smoke test API desplegada' . bash scripts/smoke_deployed.sh
else skip_step 'Smoke test API desplegada' 'API_URL no definido'; fi
cat >> "$OUT" <<'EOF'

## Límites de esta ejecución

Las comprobaciones omitidas no se consideran aprobadas. Esta ejecución no certifica hardware ESP32/cámaras, broker MQTT/PKI, proveedor OIDC, PostgreSQL real ni despliegue remoto si esas dependencias no están configuradas. Revisa también `AUDITORIA_CORRECCIONES_PUNTA_A_PUNTA.md`.
EOF
printf '\nInforme: %s\n' "$OUT"
exit "$FAIL"
