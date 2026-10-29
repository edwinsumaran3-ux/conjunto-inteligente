#!/usr/bin/env python3
"""Ejecutor de migraciones versionadas para la base de datos de Vigilancia.

Garantías:
  * Orden estricto y sin huecos (0001, 0002, ...).
  * Una migración aplicada NUNCA se reejecuta; si su archivo cambió (checksum
    distinto al registrado en `schema_migrations`) el proceso aborta.
  * Cada migración corre en UNA transacción: o se aplica completa o no se aplica.
  * Un advisory lock evita que dos réplicas migren a la vez.
  * `--status` y `--check` no modifican nada.

Uso:
  DB_DSN=postgresql://... python migrate.py            # aplica pendientes
  python migrate.py --status                           # lista estado
  python migrate.py --check                            # falla si hay pendientes/alteradas
  python migrate.py --write-manifest                   # regenera CHECKSUMS.sha256
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
MANIFEST = "CHECKSUMS.sha256"
FILENAME_RE = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")
LOCK_KEY = 7270001


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    path: Path
    sql: str
    checksum: str


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def discover_migrations(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    """Lee y valida el directorio de migraciones (sin tocar la base de datos)."""
    found: list[Migration] = []
    for p in sorted(directory.glob("*.sql")):
        m = FILENAME_RE.match(p.name)
        if not m:
            raise MigrationError(f"nombre de migración inválido: {p.name} (esperado NNNN_nombre.sql)")
        sql = p.read_text(encoding="utf-8")
        if not sql.strip():
            raise MigrationError(f"migración vacía: {p.name}")
        found.append(Migration(m.group(1), m.group(2), p, sql, sha256_text(sql)))
    if not found:
        raise MigrationError(f"no hay migraciones en {directory}")
    expected = [f"{i:04d}" for i in range(1, len(found) + 1)]
    actual = [m.version for m in found]
    if actual != expected:
        raise MigrationError(f"numeración con huecos o duplicados: {actual} (esperado {expected})")
    return found


def render_manifest(migrations: list[Migration]) -> str:
    return "".join(f"{m.checksum}  {m.path.name}\n" for m in migrations)


def read_manifest(directory: Path = MIGRATIONS_DIR) -> dict[str, str]:
    path = directory / MANIFEST
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, _, name = line.partition("  ")
            out[name.strip()] = digest.strip()
    return out


def verify_manifest(migrations: list[Migration], manifest: dict[str, str]) -> list[str]:
    problems: list[str] = []
    for m in migrations:
        want = manifest.get(m.path.name)
        if want is None:
            problems.append(f"{m.path.name}: ausente en {MANIFEST}")
        elif want != m.checksum:
            problems.append(f"{m.path.name}: checksum distinto al manifiesto (migración alterada)")
    for name in manifest:
        if not any(m.path.name == name for m in migrations):
            problems.append(f"{name}: está en el manifiesto pero el archivo no existe")
    return problems


def plan(migrations: list[Migration], applied: dict[str, str]) -> tuple[list[Migration], list[str]]:
    """Devuelve (pendientes, problemas). `applied` = {version: checksum} de la BD."""
    problems: list[str] = []
    known = {m.version: m for m in migrations}
    for version, checksum in applied.items():
        m = known.get(version)
        if m is None:
            problems.append(f"{version}: aplicada en la BD pero no existe el archivo (¿despliegue de versión anterior?)")
        elif m.checksum != checksum:
            problems.append(f"{version}_{m.name}: ALTERADA tras aplicarse (checksum de BD {checksum[:12]}… != archivo {m.checksum[:12]}…)")
    pending = [m for m in migrations if m.version not in applied]
    # Una pendiente con versión menor a una ya aplicada indicaría orden roto.
    if applied and pending:
        max_applied = max(applied)
        for m in pending:
            if m.version < max_applied:
                problems.append(f"{m.version}_{m.name}: pendiente pero hay versiones posteriores ya aplicadas")
    return pending, problems


BOOTSTRAP_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
  version      TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  checksum     TEXT NOT NULL,
  applied_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  execution_ms INTEGER NOT NULL DEFAULT 0
)
"""


async def _connect(dsn: str, wait_s: int):
    import asyncpg  # import diferido: las pruebas unitarias no lo necesitan

    deadline = time.monotonic() + wait_s
    last: Exception | None = None
    while True:
        try:
            return await asyncpg.connect(dsn, timeout=10)
        except Exception as exc:  # noqa: BLE001 - reintento hasta agotar plazo
            last = exc
            if time.monotonic() >= deadline:
                raise MigrationError(f"no se pudo conectar a la base de datos: {last}") from exc
            await asyncio.sleep(2)


async def run(dsn: str, *, status_only: bool, check: bool, wait_s: int) -> int:
    migrations = discover_migrations()
    problems_manifest = verify_manifest(migrations, read_manifest())
    if problems_manifest:
        print("MANIFIESTO INCONSISTENTE:\n  " + "\n  ".join(problems_manifest), file=sys.stderr)
        return 2
    conn = await _connect(dsn, wait_s)
    try:
        await conn.execute("SELECT pg_advisory_lock($1)", LOCK_KEY)
        await conn.execute(BOOTSTRAP_SQL)
        rows = await conn.fetch("SELECT version, checksum FROM schema_migrations")
        applied = {r["version"]: r["checksum"] for r in rows}
        pending, problems = plan(migrations, applied)
        if problems:
            print("PROBLEMAS DE MIGRACIÓN:\n  " + "\n  ".join(problems), file=sys.stderr)
            return 2
        if status_only or check:
            for m in migrations:
                print(f"{'APLICADA ' if m.version in applied else 'PENDIENTE'} {m.version}_{m.name}")
            return 1 if (check and pending) else 0
        for m in pending:
            started = time.monotonic()
            try:
                async with conn.transaction():
                    await conn.execute(m.sql)
                    ms = int((time.monotonic() - started) * 1000)
                    await conn.execute(
                        "INSERT INTO schema_migrations(version,name,checksum,execution_ms) VALUES($1,$2,$3,$4)",
                        m.version, m.name, m.checksum, ms,
                    )
            except Exception as exc:  # noqa: BLE001
                print(f"FALLÓ {m.version}_{m.name} (revertida): {exc}", file=sys.stderr)
                return 3
            print(f"OK {m.version}_{m.name} ({ms} ms)")
        print(f"Migraciones al día: {len(migrations)} en total, {len(pending)} aplicadas ahora.")
        return 0
    finally:
        try:
            await conn.execute("SELECT pg_advisory_unlock($1)", LOCK_KEY)
        finally:
            await conn.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dsn", default=os.getenv("DB_DSN", ""))
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--wait", type=int, default=int(os.getenv("DB_WAIT_SECONDS", "60")))
    ap.add_argument("--write-manifest", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.write_manifest:
            (MIGRATIONS_DIR / MANIFEST).write_text(render_manifest(discover_migrations()), encoding="utf-8")
            print(f"{MANIFEST} regenerado")
            return 0
        if not args.dsn:
            print("falta DB_DSN / --dsn", file=sys.stderr)
            return 2
        return asyncio.run(run(args.dsn, status_only=args.status, check=args.check, wait_s=args.wait))
    except MigrationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
