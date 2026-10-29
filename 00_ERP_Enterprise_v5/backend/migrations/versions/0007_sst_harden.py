"""sst_harden"""
from backend.migrations._sqlrun import run_sql_file
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None
def upgrade(): run_sql_file("migrations/sql/20261015_007_sst_harden.sql")
def downgrade(): raise RuntimeError("downgrade no soportado (migraciones SQL forward-only)")
