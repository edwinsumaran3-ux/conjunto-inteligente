"""dian_submissions"""
from backend.migrations._sqlrun import run_sql_file
revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None
def upgrade(): run_sql_file("migrations/sql/20261017_009_dian_submissions.sql")
def downgrade(): raise RuntimeError("downgrade no soportado (migraciones SQL forward-only)")
