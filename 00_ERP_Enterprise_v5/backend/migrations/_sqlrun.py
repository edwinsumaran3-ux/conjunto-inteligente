"""Ejecuta un archivo .sql completo (varias sentencias, bloques $$) dentro de la transacción de Alembic."""
import pathlib
from alembic import op
from sqlalchemy.util import await_only
ROOT = pathlib.Path(__file__).resolve().parents[2]
def run_sql_file(rel: str) -> None:
    sql = (ROOT / rel).read_text(encoding="utf-8")
    raw = op.get_bind().connection.dbapi_connection          # AdaptedConnection de asyncpg
    await_only(raw._connection.execute(sql))                   # protocolo simple: admite múltiples sentencias
