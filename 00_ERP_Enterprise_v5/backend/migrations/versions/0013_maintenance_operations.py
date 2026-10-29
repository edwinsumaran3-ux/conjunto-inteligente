from backend.migrations._sqlrun import run_sql_file

revision = "0013_maintenance_operations"
down_revision = "0012_edge_transport_replay_retention"
branch_labels = None
depends_on = None


def upgrade():
    run_sql_file("migrations/sql/20261027_013_maintenance_operations.sql")


def downgrade():
    raise RuntimeError("downgrade no soportado (migraciones SQL forward-only)")
