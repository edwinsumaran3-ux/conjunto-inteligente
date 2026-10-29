#!/usr/bin/env python3
"""Auditoría estática del repositorio. No necesita dependencias ni red (solo la biblioteca estándar).
Comprueba: (1) sintaxis de todo el Python, (2) cadena de migraciones Alembic (cabeza única, sin padres rotos),
(3) imports internos que no resuelven. NO sustituye a las pruebas: no ejecuta el código.
Uso: python3 scripts/auditoria_estatica.py   → escribe docs/VERIFICACION_ESTATICA_<fecha>.md y devuelve 1 si hay hallazgos."""
import ast, collections, datetime, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SKIP = ('node_modules', '__pycache__', '.git', 'legacy_reference', '.venv')
IMPORT_ROOTS = {  # base -> paquete interno de nivel superior
    'services/ai-agent/conjunto-ai-block2': 'app', '00_ERP_Enterprise_v5/backend': 'app',
    'edge/gateway': 'conjunto', '00_ERP_Enterprise_v5': 'agents',
}
findings, lines = [], []
def out(s=''): lines.append(s); print(s)

py = [os.path.join(d, f) for d, _, fs in os.walk(ROOT) if not any(s in d for s in SKIP) for f in fs if f.endswith('.py')]
trees, bad = {}, []
for f in py:
    try: trees[f] = ast.parse(open(f, encoding='utf-8').read(), f)
    except Exception as e: bad.append((os.path.relpath(f, ROOT), str(e)[:100]))
out(f'# Auditoría estática · {datetime.date.today()}\n')
out(f'| Comprobación | Resultado |\n|---|---|')
out(f'| Archivos Python analizados | {len(py)} |')
out(f'| Errores de sintaxis | {len(bad)} |'); findings += [f'sintaxis: {b}' for b in bad]

def const(n, name):
    if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in n.targets): return n.value
    if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id == name: return n.value
revs = collections.defaultdict(dict)
for f, t in trees.items():
    if '/versions/' not in f: continue
    r = dr = None
    for n in t.body:
        v = const(n, 'revision');  r = v.value if isinstance(v, ast.Constant) else r
        v = const(n, 'down_revision')
        if v is not None: dr = ast.literal_eval(v)
    if r: revs[os.path.dirname(f)][r] = dr
for d, m in revs.items():
    parents = lambda x: [x] if isinstance(x, str) else list(x or [])
    heads = set(m) - {p for x in m.values() for p in parents(x)}
    broken = [(r, p) for r, x in m.items() for p in parents(x) if p not in m]
    out(f'| Migraciones `{os.path.relpath(d, ROOT)}` | {len(m)} revisiones · cabezas: {sorted(heads)} · padres inexistentes: {len(broken)} |')
    if len(heads) != 1: findings.append(f'migraciones: {len(heads)} cabezas en {d}')
    findings += [f'migración {r} apunta a {p}, que no existe' for r, p in broken]

def exists(mod, base):
    p = os.path.join(ROOT, base, *mod.split('.')); return os.path.isfile(p + '.py') or os.path.isdir(p)
unres = []
for f, t in trees.items():
    rel = os.path.relpath(f, ROOT)
    base = next((b for b in sorted(IMPORT_ROOTS, key=len, reverse=True) if rel.startswith(b + '/')), None)
    if not base: continue
    top = IMPORT_ROOTS[base]
    for n in ast.walk(t):
        mods = [n.module] if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module else [a.name for a in n.names] if isinstance(n, ast.Import) else []
        unres += [(rel, m) for m in mods if m.split('.')[0] == top and not exists(m, base)]
out(f'| Imports internos que no resuelven | {len(unres)} |'); findings += [f'import roto: {a} → {b}' for a, b in unres[:20]]
out('\nLimitación: esto es análisis estático. No prueba comportamiento, base de datos, red ni hardware.')
if findings: out('\n## Hallazgos\n' + '\n'.join(f'- {x}' for x in findings))
os.makedirs(os.path.join(ROOT, 'docs'), exist_ok=True)
open(os.path.join(ROOT, 'docs', f'VERIFICACION_ESTATICA_{datetime.date.today()}.md'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
sys.exit(1 if findings else 0)
