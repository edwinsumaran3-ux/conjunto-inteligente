"""outbox_dispatcher"""
from backend.migrations._sqlrun import run_sql_file
revision = "0002"
down_revision = '0001'
branch_labels = None
depends_on = None
def upgrade(): run_sql_file("migrations/sql/20261011_002_outbox_dispatcher.sql")
def downgrade(): raise RuntimeError("downgrade no soportado (migraciones SQL forward-only)")
