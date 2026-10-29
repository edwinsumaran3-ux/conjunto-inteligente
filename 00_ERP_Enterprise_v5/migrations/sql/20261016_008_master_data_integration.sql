-- 008: datos maestros que el código lee y ahora tienen API (políticas neuronales, rutas de inferencia, rollout edge).
-- allowed_decisions se usa como conjunto (set(policy['allowed_decisions'])): con text, set('abc') daba caracteres sueltos.
DO $$ BEGIN   -- idempotente: la 006 regenerada ya puede traer text[] (anotación list[str] de la API de políticas)
  IF (SELECT data_type FROM information_schema.columns WHERE table_name='agent_neural_policies' AND column_name='allowed_decisions') = 'text' THEN
    ALTER TABLE agent_neural_policies ALTER COLUMN allowed_decisions TYPE text[] USING CASE WHEN allowed_decisions IS NULL THEN ARRAY[]::text[] ELSE string_to_array(allowed_decisions, ',') END;
  END IF; END $$;
ALTER TABLE agent_neural_policies ALTER COLUMN allowed_decisions SET NOT NULL, ALTER COLUMN allowed_decisions SET DEFAULT ARRAY[]::text[],
  ALTER COLUMN policy_id SET DEFAULT gen_random_uuid(), ALTER COLUMN policy_id SET NOT NULL, ALTER COLUMN enabled SET DEFAULT true, ALTER COLUMN enabled SET NOT NULL,
  ALTER COLUMN min_confidence SET NOT NULL, ALTER COLUMN model_id SET NOT NULL, ALTER COLUMN agent SET NOT NULL, ALTER COLUMN purpose SET NOT NULL, ALTER COLUMN environment SET NOT NULL;
ALTER TABLE agent_neural_policies ADD CONSTRAINT chk_neural_policy_conf CHECK (min_confidence BETWEEN 0 AND 1);
CREATE UNIQUE INDEX IF NOT EXISTS ux_neural_policy ON agent_neural_policies(tenant_id,agent,purpose,environment);

ALTER TABLE ml_inference_routes ALTER COLUMN traffic_percent SET NOT NULL, ALTER COLUMN model_id SET NOT NULL, ALTER COLUMN environment SET NOT NULL;
ALTER TABLE ml_inference_routes ADD CONSTRAINT chk_route_traffic CHECK (traffic_percent BETWEEN 0 AND 100);
CREATE UNIQUE INDEX IF NOT EXISTS ux_inference_route ON ml_inference_routes(tenant_id,model_id,environment);

ALTER TABLE edge_rollout_policies ALTER COLUMN enabled SET DEFAULT true, ALTER COLUMN enabled SET NOT NULL, ALTER COLUMN require_attestation SET DEFAULT true, ALTER COLUMN require_attestation SET NOT NULL,
  ALTER COLUMN require_rollback_artifact SET DEFAULT true, ALTER COLUMN require_rollback_artifact SET NOT NULL, ALTER COLUMN max_concurrent SET DEFAULT 1, ALTER COLUMN max_concurrent SET NOT NULL,
  ALTER COLUMN min_healthy_percent SET NOT NULL, ALTER COLUMN max_failure_percent SET NOT NULL, ALTER COLUMN platform SET NOT NULL, ALTER COLUMN ring SET NOT NULL;
ALTER TABLE edge_rollout_policies ADD CONSTRAINT chk_rollout_pct CHECK (min_healthy_percent BETWEEN 0 AND 100 AND max_failure_percent BETWEEN 0 AND 100 AND max_concurrent >= 1);
CREATE UNIQUE INDEX IF NOT EXISTS ux_rollout_policy ON edge_rollout_policies(tenant_id,platform,ring);
