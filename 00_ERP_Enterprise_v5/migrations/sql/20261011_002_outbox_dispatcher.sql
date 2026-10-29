-- Additive migration for the tenant-scoped outbox dispatcher.
-- Apply through the project's controlled migration process after 001_outbox_events.sql.
-- Does not rename/drop existing columns or change existing event data.
ALTER TABLE outbox_events
    ADD COLUMN IF NOT EXISTS available_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE outbox_events
    ADD COLUMN IF NOT EXISTS locked_at timestamptz NULL;

CREATE INDEX IF NOT EXISTS ix_outbox_due_by_tenant
    ON outbox_events (tenant_id, available_at, created_at, id)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS ix_outbox_expired_processing_by_tenant
    ON outbox_events (tenant_id, locked_at, created_at, id)
    WHERE status = 'processing';
