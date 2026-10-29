from alembic import op

from backend.migrations._sqlrun import run_sql_file

revision = "0012_edge_transport_replay_retention"
down_revision = "0011_edge_telemetry_ingest_limits"
branch_labels = None
depends_on = None


def upgrade():
    run_sql_file("migrations/sql/20261020_012_edge_transport_replay_retention.sql")


def downgrade():
    raise RuntimeError("downgrade no soportado (migraciones SQL forward-only)")
