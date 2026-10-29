from alembic import op

from backend.migrations._sqlrun import run_sql_file

revision = "0010_edge_transport_replay_indexes"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    run_sql_file("migrations/sql/20261018_010_edge_transport_replay_indexes.sql")


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_edge_replays_tenant_device_nonce")
    op.execute("DROP INDEX IF EXISTS ix_edge_replays_tenant_device_sequence")
