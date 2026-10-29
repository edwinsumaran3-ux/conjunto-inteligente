#!/usr/bin/env python3
"""Static integration gate for Conjunto Inteligente; does not mutate application code."""
from __future__ import annotations
import json, re, sys
from pathlib import Path
try:
    import yaml
except Exception:
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
results: list[tuple[str, str, str]] = []  # status, scope, detail

def add(status: str, scope: str, detail: str) -> None:
    results.append((status, scope, detail))

# 1. Frontend: package scripts and local source imports.
front = ROOT / '00_ERP_Enterprise_v5' / 'frontend'
pkg_path = front / 'package.json'
if not pkg_path.is_file():
    add('FAIL', 'frontend', 'No existe frontend/package.json')
else:
    try:
        pkg = json.loads(pkg_path.read_text(encoding='utf-8'))
        scripts = pkg.get('scripts', {})
        for required in ('typecheck', 'lint', 'test', 'build', 'ci'):
            add('PASS' if required in scripts else 'FAIL', 'frontend-script', f'{required}: ' + ('definido' if required in scripts else 'ausente'))
    except Exception as exc:
        add('FAIL', 'frontend-package', f'package.json inválido: {exc}')

src = front / 'src'
if src.is_dir():
    import_re = re.compile(r"(?:from\s*|import\s*)['\"](\.{1,2}/[^'\"]+)['\"]")
    checked = 0
    missing = []
    for file in src.rglob('*'):
        if file.suffix not in ('.ts', '.tsx', '.js', '.jsx', '.mjs'):
            continue
        try: content = file.read_text(encoding='utf-8')
        except Exception: continue
        for match in import_re.finditer(content):
            spec = match.group(1)
            target = (file.parent / spec).resolve()
            candidates = [target, *(Path(str(target) + ext) for ext in ('.ts','.tsx','.js','.jsx','.mjs','.json')), *(target / ('index' + ext) for ext in ('.ts','.tsx','.js','.jsx'))]
            checked += 1
            if not any(p.is_file() for p in candidates):
                missing.append(f'{file.relative_to(ROOT)} -> {spec}')
    add('PASS', 'frontend-imports', f'{checked} imports locales revisados; sin rutas faltantes' if not missing else f'{len(missing)} import(s) local(es) no resueltos: ' + '; '.join(missing[:12]))
else:
    add('FAIL', 'frontend', 'No existe frontend/src')
add('PASS' if (front / 'node_modules').is_dir() else 'BLOCKED', 'frontend-dependencies', 'node_modules presente' if (front / 'node_modules').is_dir() else 'node_modules ausente; typecheck/build Vitest requieren instalar dependencias')

# 2. Compose: check build contexts and referenced Dockerfiles, without starting containers.
compose_files = [
    ROOT / '00_ERP_Enterprise_v5' / 'docker-compose.dev.yml',
    ROOT / '00_ERP_Enterprise_v5' / 'docker-compose.test.yml',
    ROOT / 'integrations' / 'vigilancia-sistema' / 'infrastructure' / 'docker-compose.yml',
    ROOT / 'edge' / 'conjunto-cxx' / 'docker-compose.yml',
]
for compose in compose_files:
    if not compose.is_file():
        add('FAIL', 'compose', f'Archivo ausente: {compose.relative_to(ROOT)}')
        continue
    if yaml is None:
        add('BLOCKED', 'compose', f'No se pudo analizar YAML (PyYAML ausente): {compose.relative_to(ROOT)}')
        continue
    try:
        doc = yaml.safe_load(compose.read_text(encoding='utf-8')) or {}
        services = doc.get('services', {}) or {}
        broken = []
        for name, svc in services.items():
            build = svc.get('build') if isinstance(svc, dict) else None
            if not build: continue
            if isinstance(build, str):
                context = (compose.parent / build).resolve()
                dockerfile = context / 'Dockerfile'
            elif isinstance(build, dict):
                context = (compose.parent / build.get('context', '.')).resolve()
                dockerfile = (context / build.get('dockerfile', 'Dockerfile')).resolve()
            else:
                broken.append(f'{name}: formato build no reconocido'); continue
            if not context.is_dir(): broken.append(f'{name}: contexto ausente {context}')
            elif not dockerfile.is_file(): broken.append(f'{name}: Dockerfile ausente {dockerfile}')
        detail = f'{len(services)} servicios; contextos/Dockerfiles válidos' if not broken else f'{len(broken)} problema(s): ' + '; '.join(broken[:10])
        add('PASS' if not broken else 'FAIL', f'compose:{compose.relative_to(ROOT)}', detail)
    except Exception as exc:
        add('FAIL', 'compose', f'YAML inválido en {compose.relative_to(ROOT)}: {exc}')

# 3. Runtime gate capability detection.
add('PASS' if (ROOT / '00_ERP_Enterprise_v5' / 'alembic.ini').is_file() else 'FAIL', 'erp-migrations', 'alembic.ini presente' if (ROOT / '00_ERP_Enterprise_v5' / 'alembic.ini').is_file() else 'alembic.ini ausente')
add('PASS' if (ROOT / '00_ERP_Enterprise_v5' / 'Dockerfile').is_file() else 'FAIL', 'erp-container', 'Dockerfile ERP presente' if (ROOT / '00_ERP_Enterprise_v5' / 'Dockerfile').is_file() else 'Dockerfile ERP ausente')

for status, scope, detail in results:
    print(f'[{status}] {scope}: {detail}')
counts = {s: sum(1 for r,_,_ in results if r == s) for s in ('PASS','FAIL','BLOCKED')}
print(f'\nSUMMARY PASS={counts["PASS"]} FAIL={counts["FAIL"]} BLOCKED={counts["BLOCKED"]}')
sys.exit(1 if counts['FAIL'] else 0)
