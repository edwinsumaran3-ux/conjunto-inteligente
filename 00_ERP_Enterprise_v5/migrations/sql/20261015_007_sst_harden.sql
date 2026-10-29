-- 007: SST. Tablas maestras definidas a mano (el motor las lee con SELECT *: columnas/tipos/defaults salen del contrato del dominio:
-- rules_engine, work_permit, coverage, authority). La 006 generada NO las incluye (tools/gen_migration.py las excluye).
CREATE TABLE IF NOT EXISTS sst_rules(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, jurisdiction text NOT NULL, activity_type text NOT NULL, rule_key text NOT NULL, version integer NOT NULL DEFAULT 1,
  definition jsonb NOT NULL DEFAULT '{"requirements": []}', effective_from timestamptz NOT NULL DEFAULT now(), expires_at timestamptz, approved_by uuid, created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(tenant_id,jurisdiction,activity_type,rule_key,version));
CREATE TABLE IF NOT EXISTS sst_evidence(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, evidence_type text NOT NULL, scope_kind text, scope_id uuid, status text NOT NULL DEFAULT 'pending_review',
  issued_at timestamptz, expires_at timestamptz, uploaded_by uuid, reviewed_by uuid, reviewed_at timestamptz, review_note text, file_ref text, created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (reviewed_by IS NULL OR uploaded_by IS NULL OR reviewed_by <> uploaded_by));      -- doble control en la base, no solo en la API
CREATE TABLE IF NOT EXISTS sst_exceptions(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, activity_id uuid NOT NULL, requirement_key text, approval_id uuid, approved_by uuid,
  status text NOT NULL DEFAULT 'approved', expires_at timestamptz, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS sst_asset_registry(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, asset_type text NOT NULL, zone_id uuid, capacity_units numeric(20,4) CHECK (capacity_units IS NULL OR capacity_units >= 0),
  inspection_valid_until timestamptz, expires_at timestamptz, status text NOT NULL DEFAULT 'available', created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS sst_ats(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, version integer NOT NULL DEFAULT 1, title text, steps jsonb NOT NULL DEFAULT '[]',
  signatures jsonb NOT NULL DEFAULT '[]', required_signers jsonb NOT NULL DEFAULT '[]', created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS sst_work_permits(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, status text NOT NULL DEFAULT 'draft', activity_id uuid, ats_id uuid, ats_version integer NOT NULL DEFAULT 1, permit_type text,
  zone_id uuid, contractor_id uuid, worker_ids jsonb NOT NULL DEFAULT '[]', approval_id uuid, valid_from timestamptz, valid_to timestamptz, created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to > valid_from));
CREATE TABLE IF NOT EXISTS sst_authority_matrix(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, version integer NOT NULL DEFAULT 1, matrix jsonb NOT NULL, approved_by uuid, created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(tenant_id,version));          -- {"rules":[{request_type,risk_levels,approver_role,...}]} (domain/authority.py)
CREATE INDEX IF NOT EXISTS ix_sst_evidence_tenant ON sst_evidence(tenant_id,evidence_type);
CREATE INDEX IF NOT EXISTS ix_sst_assets_tenant ON sst_asset_registry(tenant_id,asset_type);

DO $$ DECLARE t text; BEGIN
  FOR t IN SELECT unnest(ARRAY['sst_rules','sst_evidence','sst_exceptions','sst_asset_registry','sst_ats','sst_work_permits','sst_authority_matrix']) LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t); EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS %I ON %I', t||'_tenant_isolation', t);
    EXECUTE format('CREATE POLICY %I ON %I USING (tenant_id = app_tenant()) WITH CHECK (tenant_id = app_tenant())', t||'_tenant_isolation', t);
  END LOOP; END $$;

-- Columnas de actor/entidad que el código maneja como UUID (la inferencia por anotaciones las dejó como text) y columnas leídas con SELECT *
ALTER TABLE sst_activities ALTER COLUMN requester_id TYPE uuid USING requester_id::uuid;
ALTER TABLE sst_approvals ALTER COLUMN requester_id TYPE uuid USING requester_id::uuid, ALTER COLUMN primary_id TYPE uuid USING primary_id::uuid, ALTER COLUMN backup_id TYPE uuid USING backup_id::uuid;
ALTER TABLE sst_approvals ADD COLUMN IF NOT EXISTS version integer NOT NULL DEFAULT 1;       -- decide() lee r["version"]
ALTER TABLE sst_approval_tokens ALTER COLUMN recipient_id TYPE uuid USING recipient_id::uuid;
ALTER TABLE sst_temporary_assignments ALTER COLUMN proposed_by TYPE uuid USING proposed_by::uuid, ALTER COLUMN verified_by TYPE uuid USING verified_by::uuid;
ALTER TABLE sst_requirement_evaluations ALTER COLUMN rule_id TYPE uuid USING rule_id::uuid, ALTER COLUMN evidence_id TYPE uuid USING evidence_id::uuid;
