#!/usr/bin/env python3
"""Verificador ESTÁTICO del esquema (solo biblioteca estándar).

No sustituye ejecutar las migraciones contra PostgreSQL (eso lo hace `migrate.py` / CI con un Postgres real),
pero detecta sin base de datos los errores más comunes:
  * sintaxis desbalanceada (paréntesis, comillas, bloques $$);
  * tablas sin PRIMARY KEY, FKs/índices/triggers que apuntan a tablas, columnas o funciones inexistentes;
  * sentencias destructivas (DROP TABLE/COLUMN, TRUNCATE, DELETE, DROP INDEX/TRIGGER) fuera de la lista permitida;
  * nombres de índice o constraint duplicados;
  * INSERT/UPDATE del código Python de los servicios contra tablas o columnas que el esquema no define.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]  # integrations/vigilancia-sistema

# Sentencias destructivas permitidas explícitamente (con su justificación en la migración).
# Tablas creadas fuera de las migraciones (bootstrap de migrate.py).
EXTERNAL_TABLES = {"schema_migrations"}

ALLOWED_DESTRUCTIVE = [
    r"ALTER TABLE events DROP CONSTRAINT IF EXISTS events_device_id_sequence_number_key",
]
DESTRUCTIVE = re.compile(r"^(DROP\s+(TABLE|COLUMN|INDEX|TRIGGER|FUNCTION|SCHEMA|VIEW)|TRUNCATE|DELETE\s+FROM)\b|\bDROP\s+COLUMN\b|\bDROP\s+CONSTRAINT\b", re.I)


@dataclass
class Table:
    name: str
    columns: set[str] = field(default_factory=set)
    has_pk: bool = False
    migration: str = ""


def strip_sql(sql: str) -> list[str]:
    """Divide en sentencias de nivel superior respetando comillas, comentarios y $tag$...$tag$."""
    out: list[str] = []
    buf: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        if c == "-" and sql.startswith("--", i):
            j = sql.find("\n", i)
            i = n if j == -1 else j
            continue
        if c == "/" and sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            if j == -1:
                raise ValueError("comentario de bloque sin cerrar")
            i = j + 2
            continue
        if c == "'":
            j = i + 1
            while True:
                j = sql.find("'", j)
                if j == -1:
                    raise ValueError("comilla simple sin cerrar")
                if sql.startswith("''", j):
                    j += 2
                    continue
                break
            buf.append(sql[i:j + 1])
            i = j + 1
            continue
        if c == "$":
            m = re.match(r"\$([A-Za-z_]\w*)?\$", sql[i:])
            if m:
                tag = m.group(0)
                j = sql.find(tag, i + len(tag))
                if j == -1:
                    raise ValueError(f"bloque {tag} sin cerrar")
                buf.append(sql[i:j + len(tag)])
                i = j + len(tag)
                continue
        if c == ";":
            stmt = "".join(buf).strip()
            if stmt:
                out.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return out


def _mask_literals(stmt: str) -> str:
    """Sustituye literales y bloques $$ por espacios para analizar la estructura sin falsos positivos."""
    stmt = re.sub(r"\$([A-Za-z_]\w*)?\$.*?\$\1\$", lambda m: " " * len(m.group(0)), stmt, flags=re.S) if False else stmt
    out, i, n = [], 0, len(stmt)
    while i < n:
        c = stmt[i]
        if c == "'":
            j = i + 1
            while True:
                j = stmt.find("'", j)
                if stmt.startswith("''", j):
                    j += 2
                    continue
                break
            out.append(" " * (j - i + 1))
            i = j + 1
        elif c == "$":
            m = re.match(r"\$([A-Za-z_]\w*)?\$", stmt[i:])
            if m:
                tag = m.group(0)
                j = stmt.find(tag, i + len(tag))
                out.append(" " * (j + len(tag) - i))
                i = j + len(tag)
            else:
                out.append(c)
                i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _match_paren(s: str, start: int) -> int:
    depth = 0
    for k in range(start, len(s)):
        if s[k] == "(":
            depth += 1
        elif s[k] == ")":
            depth -= 1
            if depth == 0:
                return k
    raise ValueError("paréntesis sin cerrar")


def _split_top(s: str) -> list[str]:
    parts, depth, cur = [], 0, []
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur).strip())
    return parts


def _cols(s: str) -> list[str]:
    return [c.strip().strip('"') for c in s.split(",") if c.strip()]


class Schema:
    def __init__(self) -> None:
        self.tables: dict[str, Table] = {}
        self.functions: set[str] = set()
        self.index_names: dict[str, str] = {}
        self.constraint_names: dict[str, str] = {}
        self.problems: list[str] = []

    def err(self, mig: str, msg: str) -> None:
        self.problems.append(f"{mig}: {msg}")

    # ---------- análisis por sentencia ----------
    def _check_fk(self, mig: str, table: str, text: str) -> None:
        for m in re.finditer(r"REFERENCES\s+(\w+)\s*\(([^)]*)\)", text, re.I):
            tgt, cols = m.group(1), _cols(m.group(2))
            if tgt not in self.tables:
                self.err(mig, f"FK de {table} apunta a tabla inexistente {tgt}")
                continue
            for c in cols:
                if c not in self.tables[tgt].columns:
                    self.err(mig, f"FK de {table} apunta a columna inexistente {tgt}.{c}")

    def _create_table(self, mig: str, stmt: str) -> None:
        m = re.match(r"CREATE TABLE\s+(?:IF NOT EXISTS\s+)?(\w+)\s*\(", stmt, re.I)
        name = m.group(1)
        if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
            self.err(mig, f"nombre de tabla no snake_case: {name}")
        end = _match_paren(stmt, m.end() - 1)
        body = stmt[m.end():end]
        existed = name in self.tables
        t = self.tables.setdefault(name, Table(name, migration=mig))
        masked = _mask_literals(body)
        for item_masked, item in zip(_split_top(masked), _split_top(body)):
            head = item_masked.split(None, 1)[0].upper() if item_masked.split() else ""
            if head in ("PRIMARY", "UNIQUE", "FOREIGN", "CHECK", "CONSTRAINT", "EXCLUDE"):
                if re.search(r"PRIMARY\s+KEY", item_masked, re.I):
                    t.has_pk = True
                pk = re.search(r"(?:PRIMARY KEY|UNIQUE|FOREIGN KEY)\s*\(([^)]*)\)", item_masked, re.I)
                if pk:
                    for c in _cols(pk.group(1)):
                        if c not in t.columns:
                            self.err(mig, f"{name}: constraint usa columna inexistente {c}")
                self._check_fk(mig, name, item_masked)
                continue
            col = item_masked.split()[0].strip('"')
            t.columns.add(col)
            if re.search(r"PRIMARY\s+KEY", item_masked, re.I):
                t.has_pk = True
            self._check_fk(mig, name, item_masked)
        if not existed and not t.has_pk:
            self.err(mig, f"tabla {name} sin PRIMARY KEY")

    def _alter_table(self, mig: str, stmt: str) -> None:
        m = re.match(r"ALTER TABLE\s+(?:ONLY\s+)?(\w+)\s+(.*)", stmt, re.I | re.S)
        tbl = m.group(1)
        if tbl not in self.tables:
            self.err(mig, f"ALTER TABLE sobre tabla inexistente {tbl}")
            return
        for am in re.finditer(r"ADD COLUMN\s+(?:IF NOT EXISTS\s+)?(\w+)", m.group(2), re.I):
            self.tables[tbl].columns.add(am.group(1))
        self._check_fk(mig, tbl, m.group(2))

    def _create_index(self, mig: str, stmt: str) -> None:
        m = re.match(r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:CONCURRENTLY\s+)?(?:IF NOT EXISTS\s+)?(\w+)\s+ON\s+(\w+)\s*(?:USING\s+\w+\s*)?\(", stmt, re.I)
        if not m:
            self.err(mig, f"CREATE INDEX no reconocido: {stmt[:70]}")
            return
        name, tbl = m.group(1), m.group(2)
        if name in self.index_names and self.index_names[name] != mig:
            self.err(mig, f"índice duplicado {name} (ya definido en {self.index_names[name]})")
        self.index_names.setdefault(name, mig)
        if tbl not in self.tables:
            self.err(mig, f"índice {name} sobre tabla inexistente {tbl}")
            return
        end = _match_paren(stmt, m.end() - 1)
        for part in _split_top(stmt[m.end():end]):
            if "(" in part:
                continue  # expresión
            col = re.split(r"\s+", part.strip())[0].strip('"')
            if col not in self.tables[tbl].columns:
                self.err(mig, f"índice {name}: columna inexistente {tbl}.{col}")

    def _add_constraint_call(self, mig: str, stmt: str) -> None:
        m = re.match(r"SELECT\s+vigia_add_constraint\s*\(\s*'(\w+)'\s*,\s*'(\w+)'\s*,\s*(\$\w*\$)(.*)\3\s*\)\s*$", stmt, re.I | re.S)
        if not m:
            self.err(mig, f"vigia_add_constraint con formato no reconocido: {stmt[:80]}")
            return
        tbl, cname, definition = m.group(1), m.group(2), m.group(4)
        if tbl not in self.tables:
            self.err(mig, f"vigia_add_constraint sobre tabla inexistente {tbl}")
            return
        if cname in self.constraint_names:
            self.err(mig, f"constraint duplicada {cname} (ya en {self.constraint_names[cname]})")
        self.constraint_names[cname] = mig
        fk = re.match(r"\s*FOREIGN KEY\s*\(([^)]*)\)", definition, re.I)
        if fk:
            for c in _cols(fk.group(1)):
                if c not in self.tables[tbl].columns:
                    self.err(mig, f"{cname}: columna inexistente {tbl}.{c}")
        self._check_fk(mig, tbl, definition)
        if not re.search(r"NOT VALID\s*$", definition.strip(), re.I) and re.match(r"\s*(CHECK|FOREIGN)", definition, re.I):
            self.err(mig, f"{cname}: debe añadirse NOT VALID (se valida en 0008)")

    def feed(self, mig: str, sql: str) -> None:
        try:
            statements = strip_sql(sql)
        except ValueError as exc:
            self.err(mig, f"SQL mal formado: {exc}")
            return
        for stmt in statements:
            masked = _mask_literals(stmt).strip()
            head = " ".join(masked.split()[:3]).upper()
            if DESTRUCTIVE.search(masked) and not any(re.fullmatch(a, " ".join(stmt.split()), re.I) for a in ALLOWED_DESTRUCTIVE):
                self.err(mig, f"sentencia destructiva no permitida: {' '.join(stmt.split())[:90]}")
                continue
            try:
                if head.startswith("CREATE TABLE"):
                    self._create_table(mig, masked if False else stmt)
                elif head.startswith("ALTER TABLE"):
                    self._alter_table(mig, stmt)
                elif re.match(r"CREATE\s+(UNIQUE\s+)?INDEX", masked, re.I):
                    self._create_index(mig, stmt)
                elif re.match(r"CREATE\s+(OR\s+REPLACE\s+)?FUNCTION\s+(\w+)", masked, re.I):
                    self.functions.add(re.match(r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(\w+)", masked, re.I).group(1))
                elif re.match(r"CREATE\s+(OR\s+REPLACE\s+)?TRIGGER", masked, re.I):
                    tm = re.match(r"CREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+(\w+)\s+.*?\bON\s+(\w+)\s+.*?EXECUTE\s+(?:FUNCTION|PROCEDURE)\s+(\w+)", masked, re.I | re.S)
                    if not tm:
                        self.err(mig, f"trigger no reconocido: {stmt[:70]}")
                    else:
                        if tm.group(2) not in self.tables:
                            self.err(mig, f"trigger {tm.group(1)} sobre tabla inexistente {tm.group(2)}")
                        if tm.group(3) not in self.functions:
                            self.err(mig, f"trigger {tm.group(1)} usa función inexistente {tm.group(3)}")
                elif head.startswith("SELECT VIGIA_ADD_CONSTRAINT"):
                    self._add_constraint_call(mig, stmt)
            except Exception as exc:  # noqa: BLE001
                self.err(mig, f"no se pudo analizar «{stmt[:60]}…»: {exc}")


def analyze(directory: Path | None = None) -> Schema:
    directory = directory or HERE / "migrations"
    schema = Schema()
    for p in sorted(directory.glob("*.sql")):
        schema.feed(p.name, p.read_text(encoding="utf-8"))
    return schema


# ---------- cruce código Python <-> esquema ----------
INSERT_RE = re.compile(r"INSERT\s+INTO\s+(\w+)\s*\(([^)]*)\)", re.I)
UPDATE_RE = re.compile(r"UPDATE\s+(\w+)\s+SET\s+(.*?)(?:\s+WHERE\b|\s+RETURNING\b|\"\"\"|'''|\"|'(?=\s*,)|$)", re.I | re.S)


def python_sql_problems(schema: Schema, root: Path = ROOT) -> list[str]:
    problems: list[str] = []
    generated_dirs = {".venv", "node_modules", ".pio", "__pycache__", ".pytest_cache", "build", "dist"}
    files = [p for p in root.rglob("*.py")
             if not generated_dirs.intersection(p.parts)
             and "tests" not in p.parts and p.name != "schema_check.py"]
    for p in files:
        text = p.read_text(encoding="utf-8")
        rel = p.relative_to(root)
        for m in INSERT_RE.finditer(text):
            tbl, cols = m.group(1), _cols(m.group(2))
            if tbl.lower() in ("values", "select") or tbl in EXTERNAL_TABLES:
                continue
            if tbl not in schema.tables:
                problems.append(f"{rel}: INSERT en tabla inexistente en el esquema: {tbl}")
                continue
            for c in cols:
                if re.fullmatch(r"\w+", c) and c not in schema.tables[tbl].columns:
                    problems.append(f"{rel}: INSERT {tbl} usa columna inexistente {c}")
        for m in UPDATE_RE.finditer(text):
            tbl = m.group(1)
            if tbl not in schema.tables:
                continue  # p.ej. texto en comentarios o docstrings
            for assign in _split_top(m.group(2)):
                lhs = assign.split("=", 1)[0].strip()
                if re.fullmatch(r"[a-z_][a-z0-9_]*", lhs) and lhs not in schema.tables[tbl].columns:
                    problems.append(f"{rel}: UPDATE {tbl} usa columna inexistente {lhs}")
    return problems


def main() -> int:
    schema = analyze()
    problems = schema.problems + python_sql_problems(schema)
    print(f"TABLAS={len(schema.tables)} INDICES={len(schema.index_names)} CONSTRAINTS_NOT_VALID={len(schema.constraint_names)} FUNCIONES={len(schema.functions)}")
    print("SCHEMA_CHECK", "PASS" if not problems else "FAIL")
    for p in problems:
        print(" -", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
