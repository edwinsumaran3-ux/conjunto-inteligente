from __future__ import annotations
import json, py_compile, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
IGNORED_DIRS={'.venv','node_modules','.pio','__pycache__','.pytest_cache','.mypy_cache','build','dist'}
errors=[]; py_count=0

def ignored(p: Path) -> bool:
    return any(part in IGNORED_DIRS for part in p.parts)

for p in ROOT.rglob('*.py'):
    if ignored(p): continue
    py_count += 1
    try: py_compile.compile(str(p), doraise=True)
    except Exception as e: errors.append(f'{p}: {e}')
for p in ROOT.rglob('*.json'):
    if ignored(p): continue
    try: json.loads(p.read_text(encoding='utf-8'))
    except Exception as e: errors.append(f'{p}: invalid json: {e}')
empty=[]
for p in ROOT.rglob('*'):
    if not ignored(p) and p.is_file() and p.stat().st_size==0: empty.append(str(p.relative_to(ROOT)))
if empty: errors.extend('empty-file:'+x for x in empty if not x.endswith('.gitkeep'))
print(f'PYTHON_FILES={py_count}')
print('VERIFY_PLATFORM', 'PASS' if not errors else 'FAIL')
if errors:
    print('\n'.join(errors)); sys.exit(1)

# ---- Verificaciones añadidas (esquema y dependencias); las anteriores permanecen intactas ----
sys.path.insert(0, str(ROOT / 'infrastructure' / 'postgres'))
extra = []
try:
    import migrate, schema_check
    ms = migrate.discover_migrations()
    extra += [f'manifest: {x}' for x in migrate.verify_manifest(ms, migrate.read_manifest())]
    sc = schema_check.analyze()
    extra += [f'schema: {x}' for x in sc.problems + schema_check.python_sql_problems(sc)]
    print(f'MIGRATIONS={len(ms)} TABLES={len(sc.tables)}')
except Exception as e:  # noqa: BLE001
    extra.append(f'schema-check crashed: {e}')
print('VERIFY_SCHEMA', 'PASS' if not extra else 'FAIL')
if extra:
    print('\n'.join(extra)); sys.exit(1)
