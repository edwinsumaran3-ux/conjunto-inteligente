-- Additive platform prerequisites for the v11 API entry point.
-- Review and apply through the controlled migration process. No existing rows are dropped.
CREATE TABLE IF NOT EXISTS tenants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name varchar(180) NOT NULL,
  is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  email varchar(254) NOT NULL, password_hash varchar(512) NOT NULL, is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(), CONSTRAINT uq_users_tenant_email UNIQUE(tenant_id,email)
);
CREATE INDEX IF NOT EXISTS ix_users_tenant_id ON users(tenant_id);
CREATE TABLE IF NOT EXISTS roles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name varchar(80) NOT NULL, CONSTRAINT uq_roles_tenant_name UNIQUE(tenant_id,name)
);
CREATE TABLE IF NOT EXISTS user_roles (
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE, role_id uuid NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  PRIMARY KEY(user_id,role_id)
);
CREATE TABLE IF NOT EXISTS idempotency_records (
  tenant_id uuid NOT NULL, idempotency_key varchar(200) NOT NULL, route varchar(240) NOT NULL,
  request_hash char(64) NOT NULL, status varchar(20) NOT NULL CHECK(status IN ('in_progress','completed')),
  response_status integer, response_body jsonb, created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz, expires_at timestamptz NOT NULL,
  PRIMARY KEY(tenant_id,idempotency_key,route), CHECK((status='completed')=(response_status IS NOT NULL AND response_body IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS ix_idempotency_expiry ON idempotency_records(expires_at);
CREATE TABLE IF NOT EXISTS audit_log (
  id uuid PRIMARY KEY, tenant_id uuid NOT NULL, actor_id uuid, action varchar(160) NOT NULL,
  entity_type varchar(120) NOT NULL, entity_id varchar(180) NOT NULL, before_state jsonb, after_state jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_audit_log_tenant_created ON audit_log(tenant_id,created_at DESC);
CREATE TABLE IF NOT EXISTS realtime_events (
  event_id uuid PRIMARY KEY, tenant_id uuid NOT NULL, sequence bigserial NOT NULL,
  topic varchar(160) NOT NULL, correlation_id varchar(160), payload jsonb NOT NULL,
  payload_sha256 char(64) NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_realtime_tenant_sequence UNIQUE(tenant_id,sequence)
);
CREATE INDEX IF NOT EXISTS ix_realtime_tenant_topic_seq ON realtime_events(tenant_id,topic,sequence);
CREATE TABLE IF NOT EXISTS user_totp_credentials (
  tenant_id uuid NOT NULL, user_id uuid NOT NULL, encrypted_secret text NOT NULL,
  digits smallint NOT NULL DEFAULT 6 CHECK(digits IN (6,8)), period_seconds smallint NOT NULL DEFAULT 30,
  is_enabled boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(tenant_id,user_id), FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
-- Tenant tables are RLS protected; a missing tenant setting matches no rows.
DO $$ DECLARE tbl text; BEGIN
  FOREACH tbl IN ARRAY ARRAY['users','roles','idempotency_records','audit_log','realtime_events','user_totp_credentials'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',tbl);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',tbl);
    EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I',tbl);
    EXECUTE format('CREATE POLICY tenant_isolation ON %I USING (tenant_id = NULLIF(current_setting(''app.current_tenant_id'', true), '''')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting(''app.current_tenant_id'', true), '''')::uuid)',tbl);
  END LOOP;
END $$;

-- Prevent ordinary UPDATE/DELETE operations from rewriting audit history.
CREATE OR REPLACE FUNCTION reject_audit_log_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit_log is append-only; UPDATE/DELETE is forbidden';
END;
$$;
DROP TRIGGER IF EXISTS audit_log_no_mutation ON audit_log;
CREATE TRIGGER audit_log_no_mutation
  BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION reject_audit_log_mutation();
