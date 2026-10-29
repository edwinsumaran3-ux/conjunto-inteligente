-- 004: esquema completo del Gemelo Digital / BIM / Estate (antes AUSENTE: el API referenciaba tablas que ninguna migración creaba).
-- Idempotente. Todas las tablas con RLS forzada por tenant (mismo patrón que 001/003).
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS twin_nodes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, parent_id uuid REFERENCES twin_nodes(id) ON DELETE SET NULL,  node_type varchar(40) NOT NULL, code varchar(160) NOT NULL, name varchar(240) NOT NULL, status varchar(32) NOT NULL DEFAULT 'unknown',  latitude double precision CHECK (latitude BETWEEN -90 AND 90), longitude double precision CHECK (longitude BETWEEN -180 AND 180), elevation_m double precision,  metadata jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, code)
);
CREATE INDEX IF NOT EXISTS ix_twin_nodes_parent ON twin_nodes(tenant_id,parent_id);
CREATE INDEX IF NOT EXISTS ix_twin_nodes_type ON twin_nodes(tenant_id,node_type);
ALTER TABLE twin_nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_nodes FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_nodes_tenant_isolation ON twin_nodes;
CREATE POLICY twin_nodes_tenant_isolation ON twin_nodes USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_edges (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, from_node uuid NOT NULL REFERENCES twin_nodes(id) ON DELETE CASCADE, to_node uuid NOT NULL REFERENCES twin_nodes(id) ON DELETE CASCADE, relation varchar(60) NOT NULL, metadata jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (from_node <> to_node),
  UNIQUE (tenant_id, from_node, to_node, relation)
);
ALTER TABLE twin_edges ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_edges FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_edges_tenant_isolation ON twin_edges;
CREATE POLICY twin_edges_tenant_isolation ON twin_edges USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_model_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, model_key varchar(180) NOT NULL, version varchar(80) NOT NULL, source_system varchar(120) NOT NULL, source_format varchar(40) NOT NULL, lifecycle_status varchar(32) NOT NULL DEFAULT 'DRAFT', schema_uri varchar(500), source_revision varchar(180), document_ref varchar(500), content_sha256 varchar(64), metadata jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, model_key, version)
);
ALTER TABLE twin_model_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_model_versions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_model_versions_tenant_isolation ON twin_model_versions;
CREATE POLICY twin_model_versions_tenant_isolation ON twin_model_versions USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_bindings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, node_id uuid NOT NULL REFERENCES twin_nodes(id) ON DELETE CASCADE, model_version_id uuid REFERENCES twin_model_versions(id) ON DELETE SET NULL, identifier_system varchar(80) NOT NULL, identifier_type varchar(80) NOT NULL, identifier varchar(240) NOT NULL, provenance_id uuid, confidence double precision NOT NULL DEFAULT 1 CHECK (confidence BETWEEN 0 AND 1), metadata jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, node_id, identifier_system, identifier_type, identifier)
);
CREATE INDEX IF NOT EXISTS ix_twin_bindings_ident ON twin_bindings(tenant_id,identifier);
ALTER TABLE twin_bindings ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_bindings FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_bindings_tenant_isolation ON twin_bindings;
CREATE POLICY twin_bindings_tenant_isolation ON twin_bindings USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_spatial_references (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, node_id uuid NOT NULL REFERENCES twin_nodes(id) ON DELETE CASCADE, model_version_id uuid REFERENCES twin_model_versions(id) ON DELETE SET NULL, reference_system varchar(120) NOT NULL, geometry_type varchar(40) NOT NULL DEFAULT 'POINT', geometry jsonb NOT NULL, floor_ref varchar(120), space_ref varchar(240), elevation_m double precision, provenance_id uuid, confidence double precision NOT NULL DEFAULT 1 CHECK (confidence BETWEEN 0 AND 1), created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_twin_spatial_node ON twin_spatial_references(tenant_id,node_id);
ALTER TABLE twin_spatial_references ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_spatial_references FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_spatial_references_tenant_isolation ON twin_spatial_references;
CREATE POLICY twin_spatial_references_tenant_isolation ON twin_spatial_references USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_properties (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, node_id uuid NOT NULL REFERENCES twin_nodes(id) ON DELETE CASCADE, model_version_id uuid REFERENCES twin_model_versions(id) ON DELETE SET NULL, provenance_id uuid, namespace varchar(160) NOT NULL, property_name varchar(180) NOT NULL, value_type varchar(40) NOT NULL, value jsonb, unit varchar(40), source varchar(160) NOT NULL, quality varchar(32) NOT NULL DEFAULT 'VALID', effective_from timestamptz, effective_to timestamptz, observed_at timestamptz, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_twin_properties_node ON twin_properties(tenant_id,node_id);
ALTER TABLE twin_properties ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_properties FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_properties_tenant_isolation ON twin_properties;
CREATE POLICY twin_properties_tenant_isolation ON twin_properties USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_state_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, node_id uuid NOT NULL REFERENCES twin_nodes(id) ON DELETE CASCADE, model_version_id uuid REFERENCES twin_model_versions(id) ON DELETE SET NULL, captured_at timestamptz NOT NULL DEFAULT now(), state varchar(40) NOT NULL DEFAULT 'UNKNOWN', state_data jsonb NOT NULL DEFAULT '{}'::jsonb, health_score double precision CHECK (health_score BETWEEN 0 AND 100), confidence double precision NOT NULL DEFAULT 1 CHECK (confidence BETWEEN 0 AND 1), derived_from jsonb NOT NULL DEFAULT '[]'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_twin_snapshots_node ON twin_state_snapshots(tenant_id,node_id,captured_at DESC);
ALTER TABLE twin_state_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_state_snapshots FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_state_snapshots_tenant_isolation ON twin_state_snapshots;
CREATE POLICY twin_state_snapshots_tenant_isolation ON twin_state_snapshots USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_telemetry (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, tenant_id uuid NOT NULL, node_id uuid NOT NULL REFERENCES twin_nodes(id) ON DELETE CASCADE, metric varchar(120) NOT NULL, value_double double precision NOT NULL, unit varchar(32), quality varchar(24) NOT NULL DEFAULT 'good', observed_at timestamptz NOT NULL, received_at timestamptz NOT NULL DEFAULT now(), source varchar(120) NOT NULL, correlation_id varchar(128), metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_twin_telemetry_node ON twin_telemetry(tenant_id,node_id,observed_at DESC);
ALTER TABLE twin_telemetry ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_telemetry FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_telemetry_tenant_isolation ON twin_telemetry;
CREATE POLICY twin_telemetry_tenant_isolation ON twin_telemetry USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_devices (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, node_id uuid REFERENCES twin_nodes(id) ON DELETE SET NULL, external_device_id varchar(200), device_type varchar(80) NOT NULL, manufacturer varchar(160), model varchar(160), serial_number varchar(160), firmware_version varchar(120), protocol varchar(80), status varchar(24) NOT NULL DEFAULT 'UNKNOWN', last_seen_at timestamptz, metadata jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_twin_devices_ext ON twin_devices(tenant_id,external_device_id) WHERE external_device_id IS NOT NULL;
ALTER TABLE twin_devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_devices FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_devices_tenant_isolation ON twin_devices;
CREATE POLICY twin_devices_tenant_isolation ON twin_devices USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_points (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, node_id uuid NOT NULL REFERENCES twin_nodes(id) ON DELETE CASCADE, device_id uuid REFERENCES twin_devices(id) ON DELETE SET NULL, code varchar(180) NOT NULL, name varchar(240) NOT NULL, semantic_kind varchar(100) NOT NULL, data_type varchar(40) NOT NULL DEFAULT 'float64', canonical_unit varchar(40), engineering_min double precision, engineering_max double precision, stale_after_seconds integer NOT NULL DEFAULT 300 CHECK (stale_after_seconds>0), sampling_interval_seconds integer CHECK (sampling_interval_seconds>0), metadata jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, node_id, code),
  CHECK (engineering_max IS NULL OR engineering_min IS NULL OR engineering_max>=engineering_min)
);
CREATE INDEX IF NOT EXISTS ix_twin_points_node ON twin_points(tenant_id,node_id);
ALTER TABLE twin_points ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_points FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_points_tenant_isolation ON twin_points;
CREATE POLICY twin_points_tenant_isolation ON twin_points USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_telemetry_samples (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, tenant_id uuid NOT NULL, point_id uuid NOT NULL REFERENCES twin_points(id) ON DELETE CASCADE, device_id uuid REFERENCES twin_devices(id) ON DELETE SET NULL, observed_at timestamptz NOT NULL, received_at timestamptz NOT NULL DEFAULT now(), sequence bigint, source_message_id varchar(240), source varchar(160) NOT NULL, raw_value double precision NOT NULL, raw_unit varchar(40), canonical_value double precision NOT NULL, canonical_unit varchar(40), quality varchar(32) NOT NULL, quality_reason varchar(240), correlation_id varchar(128), payload_hash varchar(64) NOT NULL, metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_twin_samples_msg ON twin_telemetry_samples(tenant_id,source_message_id) WHERE source_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_twin_samples_point ON twin_telemetry_samples(tenant_id,point_id,observed_at DESC);
ALTER TABLE twin_telemetry_samples ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_telemetry_samples FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_telemetry_samples_tenant_isolation ON twin_telemetry_samples;
CREATE POLICY twin_telemetry_samples_tenant_isolation ON twin_telemetry_samples USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_point_states (
  tenant_id uuid NOT NULL, point_id uuid NOT NULL REFERENCES twin_points(id) ON DELETE CASCADE, observed_at timestamptz NOT NULL, received_at timestamptz NOT NULL, value double precision NOT NULL, unit varchar(40), quality varchar(32) NOT NULL, quality_reason varchar(240), sample_id bigint, PRIMARY KEY (tenant_id, point_id)
);
ALTER TABLE twin_point_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_point_states FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_point_states_tenant_isolation ON twin_point_states;
CREATE POLICY twin_point_states_tenant_isolation ON twin_point_states USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_diagnostic_runs (
  diagnostic_run_id uuid PRIMARY KEY, tenant_id uuid NOT NULL, node_id uuid NOT NULL REFERENCES twin_nodes(id) ON DELETE CASCADE, window_started_at timestamptz NOT NULL, window_ended_at timestamptz NOT NULL, method varchar(80) NOT NULL, health_score double precision NOT NULL, severity varchar(24) NOT NULL, confidence double precision NOT NULL, feature_count integer NOT NULL, probable_causes jsonb NOT NULL DEFAULT '[]'::jsonb, evidence jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_twin_diag_runs_node ON twin_diagnostic_runs(tenant_id,node_id,created_at DESC);
ALTER TABLE twin_diagnostic_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_diagnostic_runs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_diagnostic_runs_tenant_isolation ON twin_diagnostic_runs;
CREATE POLICY twin_diagnostic_runs_tenant_isolation ON twin_diagnostic_runs USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_diagnostic_features (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, diagnostic_run_id uuid NOT NULL REFERENCES twin_diagnostic_runs(diagnostic_run_id) ON DELETE CASCADE, point_id uuid NOT NULL REFERENCES twin_points(id) ON DELETE CASCADE, latest_value double precision, baseline_value double precision, scale double precision, deviation_score double precision, trend_score double precision, persistence_score double precision, quality_penalty double precision, impairment_score double precision NOT NULL, evidence jsonb NOT NULL DEFAULT '{}'::jsonb
);
ALTER TABLE twin_diagnostic_features ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_diagnostic_features FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_diagnostic_features_tenant_isolation ON twin_diagnostic_features;
CREATE POLICY twin_diagnostic_features_tenant_isolation ON twin_diagnostic_features USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_diagnostic_change_points (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, diagnostic_run_id uuid NOT NULL REFERENCES twin_diagnostic_runs(diagnostic_run_id) ON DELETE CASCADE, point_id uuid NOT NULL REFERENCES twin_points(id) ON DELETE CASCADE, detected boolean NOT NULL, magnitude double precision, before_value double precision, after_value double precision, direction varchar(24), evidence jsonb NOT NULL DEFAULT '{}'::jsonb
);
ALTER TABLE twin_diagnostic_change_points ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_diagnostic_change_points FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_diagnostic_change_points_tenant_isolation ON twin_diagnostic_change_points;
CREATE POLICY twin_diagnostic_change_points_tenant_isolation ON twin_diagnostic_change_points USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_diagnostic_hypotheses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, diagnostic_run_id uuid NOT NULL REFERENCES twin_diagnostic_runs(diagnostic_run_id) ON DELETE CASCADE, code varchar(120) NOT NULL, confidence double precision NOT NULL, severity varchar(24) NOT NULL, evidence jsonb NOT NULL DEFAULT '[]'::jsonb, recommended_actions jsonb NOT NULL DEFAULT '[]'::jsonb
);
ALTER TABLE twin_diagnostic_hypotheses ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_diagnostic_hypotheses FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_diagnostic_hypotheses_tenant_isolation ON twin_diagnostic_hypotheses;
CREATE POLICY twin_diagnostic_hypotheses_tenant_isolation ON twin_diagnostic_hypotheses USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_health_assessments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, node_id uuid NOT NULL REFERENCES twin_nodes(id) ON DELETE CASCADE, assessed_at timestamptz NOT NULL, health_score double precision NOT NULL, severity varchar(24) NOT NULL, confidence double precision NOT NULL, diagnostic_run_id uuid REFERENCES twin_diagnostic_runs(diagnostic_run_id) ON DELETE SET NULL,
  UNIQUE (tenant_id, node_id)
);
ALTER TABLE twin_health_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_health_assessments FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_health_assessments_tenant_isolation ON twin_health_assessments;
CREATE POLICY twin_health_assessments_tenant_isolation ON twin_health_assessments USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS operational_anomalies (
  anomaly_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, node_id uuid REFERENCES twin_nodes(id) ON DELETE SET NULL, metric varchar(160) NOT NULL, observed_value double precision, baseline_value double precision, score double precision, severity varchar(24) NOT NULL, status varchar(24) NOT NULL DEFAULT 'open', detection_method varchar(120) NOT NULL, evidence jsonb NOT NULL DEFAULT '{}'::jsonb, correlation_id varchar(240), twin_point_id uuid REFERENCES twin_points(id) ON DELETE SET NULL, diagnostic_run_id uuid REFERENCES twin_diagnostic_runs(diagnostic_run_id) ON DELETE SET NULL, diagnostic_confidence double precision, health_impact double precision, probable_causes jsonb NOT NULL DEFAULT '[]'::jsonb, detected_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, correlation_id)
);
CREATE INDEX IF NOT EXISTS ix_anomalies_node ON operational_anomalies(tenant_id,node_id,detected_at DESC);
CREATE INDEX IF NOT EXISTS ix_anomalies_status ON operational_anomalies(tenant_id,status,detected_at DESC);
ALTER TABLE operational_anomalies ENABLE ROW LEVEL SECURITY;
ALTER TABLE operational_anomalies FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS operational_anomalies_tenant_isolation ON operational_anomalies;
CREATE POLICY operational_anomalies_tenant_isolation ON operational_anomalies USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS operational_diagnoses (
  diagnosis_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, anomaly_id uuid NOT NULL REFERENCES operational_anomalies(anomaly_id) ON DELETE CASCADE, agent varchar(160) NOT NULL, diagnosis_code varchar(120) NOT NULL, confidence double precision NOT NULL, root_cause jsonb NOT NULL DEFAULT '{}'::jsonb, evidence jsonb NOT NULL DEFAULT '{}'::jsonb, recommended_actions jsonb NOT NULL DEFAULT '[]'::jsonb, status varchar(24) NOT NULL DEFAULT 'proposed', created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE operational_diagnoses ENABLE ROW LEVEL SECURITY;
ALTER TABLE operational_diagnoses FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS operational_diagnoses_tenant_isolation ON operational_diagnoses;
CREATE POLICY operational_diagnoses_tenant_isolation ON operational_diagnoses USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_dependency_edges (
  dependency_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, source_node_id uuid NOT NULL REFERENCES twin_nodes(id) ON DELETE CASCADE, target_node_id uuid NOT NULL REFERENCES twin_nodes(id) ON DELETE CASCADE, relation varchar(80) NOT NULL, criticality double precision NOT NULL DEFAULT 1 CHECK (criticality BETWEEN 0 AND 1), propagation_factor double precision NOT NULL DEFAULT 1 CHECK (propagation_factor BETWEEN 0 AND 1), direction varchar(24) NOT NULL DEFAULT 'source_to_target', provenance_id uuid, active boolean NOT NULL DEFAULT true, metadata jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (source_node_id <> target_node_id),
  UNIQUE (tenant_id, source_node_id, target_node_id, relation)
);
ALTER TABLE twin_dependency_edges ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_dependency_edges FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_dependency_edges_tenant_isolation ON twin_dependency_edges;
CREATE POLICY twin_dependency_edges_tenant_isolation ON twin_dependency_edges USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_system_assessments (
  assessment_id uuid PRIMARY KEY, tenant_id uuid NOT NULL, system_node_id uuid NOT NULL REFERENCES twin_nodes(id) ON DELETE CASCADE, assessed_at timestamptz NOT NULL DEFAULT now(), health_score double precision NOT NULL, severity varchar(24) NOT NULL, confidence double precision NOT NULL, source_run_id uuid, impacted_nodes jsonb NOT NULL DEFAULT '[]'::jsonb, critical_paths jsonb NOT NULL DEFAULT '[]'::jsonb, evidence jsonb NOT NULL DEFAULT '{}'::jsonb
);
ALTER TABLE twin_system_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_system_assessments FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_system_assessments_tenant_isolation ON twin_system_assessments;
CREATE POLICY twin_system_assessments_tenant_isolation ON twin_system_assessments USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_failure_chains (
  chain_id uuid PRIMARY KEY, tenant_id uuid NOT NULL, diagnostic_run_id uuid NOT NULL REFERENCES twin_diagnostic_runs(diagnostic_run_id) ON DELETE CASCADE, max_gap_seconds double precision NOT NULL, chain_confidence double precision NOT NULL, claim_level varchar(40) NOT NULL, ordered_anomalies jsonb NOT NULL DEFAULT '[]'::jsonb, evidence jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, diagnostic_run_id)
);
ALTER TABLE twin_failure_chains ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_failure_chains FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_failure_chains_tenant_isolation ON twin_failure_chains;
CREATE POLICY twin_failure_chains_tenant_isolation ON twin_failure_chains USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_failure_chain_links (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, chain_id uuid NOT NULL REFERENCES twin_failure_chains(chain_id) ON DELETE CASCADE, source_anomaly_id uuid, target_anomaly_id uuid, relation varchar(80), time_gap_seconds double precision, dependency_factor double precision, confidence double precision, evidence jsonb NOT NULL DEFAULT '{}'::jsonb
);
ALTER TABLE twin_failure_chain_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_failure_chain_links FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_failure_chain_links_tenant_isolation ON twin_failure_chain_links;
CREATE POLICY twin_failure_chain_links_tenant_isolation ON twin_failure_chain_links USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_maintenance_work_requests (
  request_id uuid PRIMARY KEY, tenant_id uuid NOT NULL, diagnostic_run_id uuid NOT NULL REFERENCES twin_diagnostic_runs(diagnostic_run_id) ON DELETE CASCADE, failure_chain_id uuid REFERENCES twin_failure_chains(chain_id) ON DELETE SET NULL, asset_id uuid NOT NULL, severity varchar(24) NOT NULL, maintenance_type varchar(80) NOT NULL, estimated_cost numeric(14,2) NOT NULL DEFAULT 0, approval_required boolean NOT NULL DEFAULT true, status varchar(32) NOT NULL DEFAULT 'pending', payload jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, diagnostic_run_id, asset_id)
);
ALTER TABLE twin_maintenance_work_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_maintenance_work_requests FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_maintenance_work_requests_tenant_isolation ON twin_maintenance_work_requests;
CREATE POLICY twin_maintenance_work_requests_tenant_isolation ON twin_maintenance_work_requests USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_cde_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, model_version_id uuid REFERENCES twin_model_versions(id) ON DELETE CASCADE, document_key varchar(240) NOT NULL, filename varchar(300) NOT NULL, media_type varchar(120) NOT NULL, content_sha256 varchar(64), file_size_bytes bigint, lifecycle_state varchar(24) NOT NULL DEFAULT 'WIP', revision varchar(40) NOT NULL DEFAULT '1', discipline varchar(80), originator varchar(120), container_path varchar(500), metadata jsonb NOT NULL DEFAULT '{}'::jsonb, published_at timestamptz, created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE twin_cde_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_cde_documents FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_cde_documents_tenant_isolation ON twin_cde_documents;
CREATE POLICY twin_cde_documents_tenant_isolation ON twin_cde_documents USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_cobie_assets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, model_version_id uuid REFERENCES twin_model_versions(id) ON DELETE CASCADE, external_system varchar(80), external_id varchar(240), node_id uuid REFERENCES twin_nodes(id) ON DELETE SET NULL, name varchar(300) NOT NULL, asset_type varchar(160), serial_number varchar(160), manufacturer varchar(160), model_number varchar(160), installation_date date, warranty_start date, warranty_end date, raw_data jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE twin_cobie_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_cobie_assets FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_cobie_assets_tenant_isolation ON twin_cobie_assets;
CREATE POLICY twin_cobie_assets_tenant_isolation ON twin_cobie_assets USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_cobie_xlsx_audits (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, model_version_id uuid REFERENCES twin_model_versions(id) ON DELETE CASCADE, filename varchar(300), content_sha256 varchar(64), valid boolean NOT NULL, sheet_names jsonb NOT NULL DEFAULT '[]'::jsonb, missing_required_sheets jsonb NOT NULL DEFAULT '[]'::jsonb, component_count integer, components_missing_name integer, metadata jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE twin_cobie_xlsx_audits ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_cobie_xlsx_audits FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_cobie_xlsx_audits_tenant_isolation ON twin_cobie_xlsx_audits;
CREATE POLICY twin_cobie_xlsx_audits_tenant_isolation ON twin_cobie_xlsx_audits USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_ids_requirements (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, model_version_id uuid REFERENCES twin_model_versions(id) ON DELETE CASCADE, requirement_key varchar(160) NOT NULL, entity_type varchar(80) NOT NULL, property_name varchar(180), required boolean NOT NULL DEFAULT true, allowed_values jsonb NOT NULL DEFAULT '[]'::jsonb, created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE twin_ids_requirements ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_ids_requirements FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_ids_requirements_tenant_isolation ON twin_ids_requirements;
CREATE POLICY twin_ids_requirements_tenant_isolation ON twin_ids_requirements USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_ids_results (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, model_version_id uuid REFERENCES twin_model_versions(id) ON DELETE CASCADE, requirement_id uuid REFERENCES twin_ids_requirements(id) ON DELETE CASCADE, express_id integer, status varchar(24) NOT NULL, reason text, created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE twin_ids_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_ids_results FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_ids_results_tenant_isolation ON twin_ids_results;
CREATE POLICY twin_ids_results_tenant_isolation ON twin_ids_results USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_ifc_entities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, model_version_id uuid NOT NULL REFERENCES twin_model_versions(id) ON DELETE CASCADE, express_id integer NOT NULL, entity_type varchar(120) NOT NULL, global_id varchar(64), name varchar(500), object_type varchar(300), attributes jsonb NOT NULL DEFAULT '{}'::jsonb, properties jsonb NOT NULL DEFAULT '{}'::jsonb, node_id uuid REFERENCES twin_nodes(id) ON DELETE SET NULL,
  UNIQUE (tenant_id, model_version_id, express_id)
);
CREATE INDEX IF NOT EXISTS ix_ifc_ent_guid ON twin_ifc_entities(tenant_id,global_id);
ALTER TABLE twin_ifc_entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_ifc_entities FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_ifc_entities_tenant_isolation ON twin_ifc_entities;
CREATE POLICY twin_ifc_entities_tenant_isolation ON twin_ifc_entities USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_ifc_relations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, model_version_id uuid NOT NULL REFERENCES twin_model_versions(id) ON DELETE CASCADE, express_id integer NOT NULL, relation_type varchar(120) NOT NULL, from_express_id integer, to_express_id integer, metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (tenant_id, model_version_id, express_id, from_express_id, to_express_id)
);
ALTER TABLE twin_ifc_relations ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_ifc_relations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_ifc_relations_tenant_isolation ON twin_ifc_relations;
CREATE POLICY twin_ifc_relations_tenant_isolation ON twin_ifc_relations USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_ifc_placements (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, model_version_id uuid NOT NULL REFERENCES twin_model_versions(id) ON DELETE CASCADE, express_id integer NOT NULL, placement_express_id integer, parent_placement_express_id integer, matrix jsonb, location jsonb, coordinate_system varchar(80),
  UNIQUE (tenant_id, model_version_id, express_id)
);
ALTER TABLE twin_ifc_placements ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_ifc_placements FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_ifc_placements_tenant_isolation ON twin_ifc_placements;
CREATE POLICY twin_ifc_placements_tenant_isolation ON twin_ifc_placements USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_ifc_spatial_context (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, model_version_id uuid NOT NULL REFERENCES twin_model_versions(id) ON DELETE CASCADE, express_id integer NOT NULL, spatial_type varchar(80) NOT NULL, global_id varchar(64), name varchar(500), floorplan_node_id uuid REFERENCES twin_nodes(id) ON DELETE SET NULL, metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (tenant_id, model_version_id, express_id)
);
ALTER TABLE twin_ifc_spatial_context ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_ifc_spatial_context FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_ifc_spatial_context_tenant_isolation ON twin_ifc_spatial_context;
CREATE POLICY twin_ifc_spatial_context_tenant_isolation ON twin_ifc_spatial_context USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS twin_ifc_spatial_links (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, model_version_id uuid NOT NULL REFERENCES twin_model_versions(id) ON DELETE CASCADE, relation_express_id integer NOT NULL, relation_type varchar(120) NOT NULL, from_express_id integer, to_express_id integer, metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (tenant_id, model_version_id, relation_express_id, from_express_id, to_express_id)
);
ALTER TABLE twin_ifc_spatial_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_ifc_spatial_links FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_ifc_spatial_links_tenant_isolation ON twin_ifc_spatial_links;
CREATE POLICY twin_ifc_spatial_links_tenant_isolation ON twin_ifc_spatial_links USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS managed_properties (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, root_node_id uuid NOT NULL REFERENCES twin_nodes(id), property_type varchar(48) NOT NULL, code varchar(160) NOT NULL, name varchar(240) NOT NULL, country_code char(2), region varchar(120), city varchar(160), address_line varchar(300), postal_code varchar(32), cadastral_reference varchar(180), timezone varchar(64) NOT NULL DEFAULT 'America/Bogota', active boolean NOT NULL DEFAULT true, metadata jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, code)
);
ALTER TABLE managed_properties ENABLE ROW LEVEL SECURITY;
ALTER TABLE managed_properties FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS managed_properties_tenant_isolation ON managed_properties;
CREATE POLICY managed_properties_tenant_isolation ON managed_properties USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS managed_units (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, property_id uuid NOT NULL REFERENCES managed_properties(id) ON DELETE CASCADE, node_id uuid NOT NULL REFERENCES twin_nodes(id), unit_type varchar(48) NOT NULL, code varchar(160) NOT NULL, name varchar(240) NOT NULL, occupancy_status varchar(32) NOT NULL DEFAULT 'unknown', area_m2 double precision CHECK (area_m2>=0), metadata jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, property_id, code)
);
ALTER TABLE managed_units ENABLE ROW LEVEL SECURITY;
ALTER TABLE managed_units FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS managed_units_tenant_isolation ON managed_units;
CREATE POLICY managed_units_tenant_isolation ON managed_units USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS operational_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, event_type varchar(96) NOT NULL, severity varchar(24) NOT NULL DEFAULT 'info', status varchar(24) NOT NULL DEFAULT 'open', source_type varchar(48) NOT NULL, source_id uuid, property_id uuid REFERENCES managed_properties(id) ON DELETE SET NULL, node_id uuid REFERENCES twin_nodes(id) ON DELETE SET NULL, correlation_id varchar(128), idempotency_key varchar(220) NOT NULL, observed_at timestamptz NOT NULL, payload jsonb NOT NULL DEFAULT '{}'::jsonb, evidence jsonb NOT NULL DEFAULT '[]'::jsonb, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS ix_opev_time ON operational_events(tenant_id,observed_at DESC);
ALTER TABLE operational_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE operational_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS operational_events_tenant_isolation ON operational_events;
CREATE POLICY operational_events_tenant_isolation ON operational_events USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

CREATE TABLE IF NOT EXISTS event_actions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, event_id uuid NOT NULL REFERENCES operational_events(id) ON DELETE CASCADE, actor_type varchar(32) NOT NULL, actor_id varchar(160) NOT NULL, action varchar(96) NOT NULL, status varchar(32) NOT NULL, requires_human_approval boolean NOT NULL DEFAULT true, approval_id uuid, idempotency_key varchar(220) NOT NULL, input_hash varchar(64), result jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, idempotency_key)
);
ALTER TABLE event_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE event_actions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS event_actions_tenant_isolation ON event_actions;
CREATE POLICY event_actions_tenant_isolation ON event_actions USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

-- Archivo IFC original (necesario para que el visor 3D cargue el modelo desde el backend)
CREATE TABLE IF NOT EXISTS twin_model_files (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL,
  model_version_id uuid NOT NULL REFERENCES twin_model_versions(id) ON DELETE CASCADE,
  filename varchar(300) NOT NULL, media_type varchar(120) NOT NULL DEFAULT 'application/x-step',
  size_bytes bigint NOT NULL, content_sha256 varchar(64) NOT NULL, content bytea NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(), UNIQUE (tenant_id, model_version_id)
);
ALTER TABLE twin_model_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE twin_model_files FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS twin_model_files_tenant_isolation ON twin_model_files;
CREATE POLICY twin_model_files_tenant_isolation ON twin_model_files USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
