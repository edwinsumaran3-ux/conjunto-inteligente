"""outbox_events"""
from backend.migrations._sqlrun import run_sql_file
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None
def upgrade(): run_sql_file("backend/app/modules/digital_twin/migrations/001_outbox_events.sql")
def downgrade(): raise RuntimeError("downgrade no soportado (migraciones SQL forward-only)")
