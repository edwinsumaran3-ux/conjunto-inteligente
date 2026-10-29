"""erp_modules_schema"""
from backend.migrations._sqlrun import run_sql_file
revision = "0006"
down_revision = '0005'
branch_labels = None
depends_on = None
def upgrade(): run_sql_file("migrations/sql/20261014_006_erp_modules_schema.sql")
def downgrade(): raise RuntimeError("downgrade no soportado (migraciones SQL forward-only)")
