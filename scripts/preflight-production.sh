#!/usr/bin/env bash
# Preflight de producción (Railway + Vercel). No sustituye a dotnet build/test en CI.
set -euo pipefail
fail=0
required=(
  'ConjuntoInteligente/src/Api/ConjuntoInteligente.Api/Program.cs'
  'ConjuntoInteligente/src/Api/ConjuntoInteligente.Api/Controllers/AuthController.cs'
  'ConjuntoInteligente/src/Api/ConjuntoInteligente.Api/Infrastructure/DatabaseInitializer.cs'
  'ConjuntoInteligente/src/Api/ConjuntoInteligente.Api/Infrastructure/ConnectionStringResolver.cs'
  'ConjuntoInteligente/src/Persistence/Migrations/0001_initial.sql'
  'ConjuntoInteligente/Dockerfile'
  'ConjuntoInteligente/railway.json'
  'apps/web-admin/frontend/web-admin/vercel.json'
)
for f in "${required[@]}"; do [[ -f "$f" ]] || { echo "MISSING $f"; fail=1; }; done
if grep -R "VITE_USE_MOCK=true" -n apps/web-admin/frontend/web-admin/.env* 2>/dev/null | grep -v '\#' >/dev/null; then echo 'ERROR: mock enabled in env files'; fail=1; fi
if grep -R "X-Tenant-Id" -n apps/web-admin/frontend/web-admin/src >/dev/null 2>&1; then echo 'ERROR: frontend still sends X-Tenant-Id'; fail=1; fi
python3 - <<'PY' || fail=1
import json, re, sys
from pathlib import Path
bad = 0
for f in ['apps/web-admin/frontend/web-admin/package.json','apps/web-admin/frontend/web-admin/vercel.json',
          'ConjuntoInteligente/src/Api/ConjuntoInteligente.Api/appsettings.Production.json','ConjuntoInteligente/railway.json']:
    json.loads(Path(f).read_text(encoding='utf8'))
print('JSON configuration: OK')
# Toda ProjectReference de cada .csproj debe existir (un error aquí rompe el Docker build de Railway).
for proj in Path('ConjuntoInteligente').rglob('*.csproj'):
    for ref in re.findall(r'ProjectReference Include="([^"]+)"', proj.read_text(encoding='utf8')):
        target = (proj.parent / ref.replace('\\', '/')).resolve()
        if not target.is_file():
            print(f'ERROR: {proj} -> referencia inexistente {ref}'); bad += 1
# Toda entrada del .sln debe existir.
sln = Path('ConjuntoInteligente/ConjuntoInteligente.sln').read_text(encoding='utf8')
for rel in re.findall(r'"([^"]+\.csproj)"', sln):
    if not (Path('ConjuntoInteligente') / rel.replace('\\', '/')).is_file():
        print(f'ERROR: .sln -> proyecto inexistente {rel}'); bad += 1
s = Path('ConjuntoInteligente/src/Persistence/Migrations/0001_initial.sql').read_text()
assert 'CREATE POLICY tenant_isolation ON tenants' not in s
assert 'latitude numeric(10,7)' in s and 'longitude numeric(10,7)' in s
assert 'COMMIT;' not in s and 'BEGIN;' not in s
print('SQL migration structural checks: OK')
print('csproj/sln references:', 'OK' if not bad else f'{bad} errores')
sys.exit(1 if bad else 0)
PY
if [[ $fail -ne 0 ]]; then exit 1; fi
echo 'Production preflight: OK (dotnet build/test siguen siendo obligatorios en CI).'
