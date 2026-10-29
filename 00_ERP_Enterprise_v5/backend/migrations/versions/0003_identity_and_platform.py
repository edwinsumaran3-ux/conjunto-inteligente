"""identity_and_platform"""
from backend.migrations._sqlrun import run_sql_file
revision = "0003"
down_revision = '0002'
branch_labels = None
depends_on = None
def upgrade(): run_sql_file("migrations/sql/20261011_003_identity_and_platform.sql")
def downgrade(): raise RuntimeError("downgrade no soportado (migraciones SQL forward-only)")
