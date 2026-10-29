"""master_data_integration"""
from backend.migrations._sqlrun import run_sql_file
revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None
def upgrade(): run_sql_file("migrations/sql/20261016_008_master_data_integration.sql")
def downgrade(): raise RuntimeError("downgrade no soportado (migraciones SQL forward-only)")
