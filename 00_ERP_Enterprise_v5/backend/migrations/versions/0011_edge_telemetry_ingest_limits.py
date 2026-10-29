from alembic import op

from backend.migrations._sqlrun import run_sql_file

revision = "0011_edge_telemetry_ingest_limits"
down_revision = "0010_edge_transport_replay_indexes"
branch_labels = None
depends_on = None


def upgrade():
    run_sql_file("migrations/sql/20261019_011_edge_telemetry_ingest_limits.sql")


def downgrade():
    raise RuntimeError("downgrade no soportado (migraciones SQL forward-only)")
