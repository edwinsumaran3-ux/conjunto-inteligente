"""digital_twin_bim_schema"""
from backend.migrations._sqlrun import run_sql_file
revision = "0004"
down_revision = '0003'
branch_labels = None
depends_on = None
def upgrade(): run_sql_file("migrations/sql/20261012_004_digital_twin_bim_schema.sql")
def downgrade(): raise RuntimeError("downgrade no soportado (migraciones SQL forward-only)")
