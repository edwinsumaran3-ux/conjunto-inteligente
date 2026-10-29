-- Transactional outbox for digital-twin domain events.
-- Review/apply with the deployment's migration process; not auto-applied.
CREATE TABLE IF NOT EXISTS outbox_events (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    event_type varchar(160) NOT NULL,
    aggregate_type varchar(120) NOT NULL,
    aggregate_id varchar(180) NOT NULL,
    payload jsonb NOT NULL,
    producer varchar(120) NOT NULL DEFAULT 'api',
    status varchar(24) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'published', 'failed')),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz,
    last_error text
);
CREATE INDEX IF NOT EXISTS ix_outbox_pending_created
    ON outbox_events (created_at, id) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS ix_outbox_tenant_created
    ON outbox_events (tenant_id, created_at DESC);
ALTER TABLE outbox_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE outbox_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS outbox_events_tenant_isolation ON outbox_events;
CREATE POLICY outbox_events_tenant_isolation ON outbox_events
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
