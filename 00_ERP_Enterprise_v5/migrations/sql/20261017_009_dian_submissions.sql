-- 009: bitácora de envíos a la DIAN (frontera DIAN: cada intento se persiste con código, descripción y hash de respuesta ANTES de cambiar el estado).
CREATE TABLE IF NOT EXISTS dian_submissions(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, document_id uuid NOT NULL REFERENCES financial_documents(id), attempt integer NOT NULL,
  outcome text NOT NULL CHECK (outcome IN ('ACCEPTED','REJECTED')), response_code text, response_description text, response_hash text NOT NULL, external_id text,
  submitted_by uuid, created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id,document_id,attempt));
ALTER TABLE dian_submissions ENABLE ROW LEVEL SECURITY; ALTER TABLE dian_submissions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS dian_submissions_tenant_isolation ON dian_submissions;
CREATE POLICY dian_submissions_tenant_isolation ON dian_submissions USING (tenant_id = app_tenant()) WITH CHECK (tenant_id = app_tenant());
CREATE OR REPLACE FUNCTION dian_submissions_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'dian_submissions is append-only'; END $$;
DROP TRIGGER IF EXISTS dian_submissions_append_only ON dian_submissions;
CREATE TRIGGER dian_submissions_append_only BEFORE UPDATE OR DELETE ON dian_submissions FOR EACH ROW EXECUTE FUNCTION dian_submissions_immutable();
