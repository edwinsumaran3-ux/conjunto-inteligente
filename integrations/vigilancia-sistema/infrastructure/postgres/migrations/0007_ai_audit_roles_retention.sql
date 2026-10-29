-- 0007 · Auditoría neural ampliada, política de proveedores de IA, roles y retención.

ALTER TABLE neural_inference_audit ADD COLUMN IF NOT EXISTS input_tokens        INTEGER;
ALTER TABLE neural_inference_audit ADD COLUMN IF NOT EXISTS output_tokens       INTEGER;
ALTER TABLE neural_inference_audit ADD COLUMN IF NOT EXISTS estimated_cost_usd  NUMERIC(12,6);
ALTER TABLE neural_inference_audit ADD COLUMN IF NOT EXISTS failover_chain      JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE neural_inference_audit ADD COLUMN IF NOT EXISTS guard_verdict       TEXT;
ALTER TABLE neural_inference_audit ADD COLUMN IF NOT EXISTS circuit_state       TEXT;
ALTER TABLE neural_inference_audit ADD COLUMN IF NOT EXISTS correlation_id      TEXT;
CREATE INDEX IF NOT EXISTS ix_neural_audit_status ON neural_inference_audit(status, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_neural_audit_provider ON neural_inference_audit(provider, created_at DESC);

-- Invariante de diseño: la inferencia neural es SOLO consultiva, nunca autoridad física.
SELECT vigia_add_constraint('neural_inference_audit', 'ck_neural_audit_advisory_only', $c$CHECK (advisory_only IS TRUE) NOT VALID$c$);
SELECT vigia_add_constraint('neural_inference_audit', 'ck_neural_audit_latency', $c$CHECK (latency_ms IS NULL OR latency_ms >= 0) NOT VALID$c$);

-- Permisos explícitos por tenant y proveedor: ninguno habilitado por defecto (Ollama local es la ruta de coste mínimo).
CREATE TABLE IF NOT EXISTS ai_provider_policies (
  tenant_id          TEXT NOT NULL REFERENCES tenants(tenant_id),
  provider           TEXT NOT NULL CHECK (provider IN ('deterministic','ollama','openai','gemini','anthropic','openai_compatible')),
  allowed            BOOLEAN NOT NULL DEFAULT FALSE,
  data_classes       TEXT[] NOT NULL DEFAULT ARRAY['PUBLIC']::text[],
  monthly_budget_usd NUMERIC(12,2) CHECK (monthly_budget_usd IS NULL OR monthly_budget_usd >= 0),
  updated_by         TEXT NOT NULL DEFAULT 'system',
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, provider)
);
CREATE OR REPLACE TRIGGER trg_ai_provider_policies_touch BEFORE UPDATE ON ai_provider_policies FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- Retención del outbox ya publicado (no borra nada pendiente).
CREATE OR REPLACE FUNCTION purge_published_outbox(p_retain interval DEFAULT interval '7 days') RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
  v_deleted BIGINT;
BEGIN
  DELETE FROM event_outbox WHERE published_at IS NOT NULL AND published_at < now() - p_retain;
  GET DIAGNOSTICS v_deleted = ROW_COUNT;
  RETURN v_deleted;
END
$$;

-- Roles de grupo sin login: los servicios se asignan a ellos con sus credenciales reales.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vigia_rw') THEN CREATE ROLE vigia_rw NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vigia_ro') THEN CREATE ROLE vigia_ro NOLOGIN; END IF;
END
$$;
GRANT USAGE ON SCHEMA public TO vigia_rw, vigia_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO vigia_ro;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO vigia_rw;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO vigia_rw;
GRANT DELETE ON event_outbox, dead_letter_messages TO vigia_rw;
REVOKE UPDATE ON audit_log FROM vigia_rw;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO vigia_ro;
