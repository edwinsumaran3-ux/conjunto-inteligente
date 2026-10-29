CREATE TABLE IF NOT EXISTS edge_telemetry_ingest_limits (
  tenant_id uuid NOT NULL,
  device_id uuid NOT NULL,
  window_started_at timestamptz NOT NULL,
  request_count integer NOT NULL CHECK (request_count > 0),
  sample_count integer NOT NULL CHECK (sample_count > 0),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, device_id)
);

ALTER TABLE edge_telemetry_ingest_limits ENABLE ROW LEVEL SECURITY;
ALTER TABLE edge_telemetry_ingest_limits FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS edge_telemetry_ingest_limits_tenant_isolation
  ON edge_telemetry_ingest_limits;
CREATE POLICY edge_telemetry_ingest_limits_tenant_isolation
  ON edge_telemetry_ingest_limits
  USING (tenant_id = app_tenant())
  WITH CHECK (tenant_id = app_tenant());
