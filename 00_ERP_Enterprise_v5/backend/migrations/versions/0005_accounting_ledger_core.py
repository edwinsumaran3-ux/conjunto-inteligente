"""accounting_ledger_core"""
from backend.migrations._sqlrun import run_sql_file
revision = "0005"
down_revision = '0004'
branch_labels = None
depends_on = None
def upgrade(): run_sql_file("migrations/sql/20261014_005_accounting_ledger_core.sql")
def downgrade(): raise RuntimeError("downgrade no soportado (migraciones SQL forward-only)")
