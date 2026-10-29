"""${message}
Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
"""
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = None
depends_on = None
def upgrade(): pass
def downgrade(): raise RuntimeError("downgrade no soportado (migraciones SQL forward-only)")
