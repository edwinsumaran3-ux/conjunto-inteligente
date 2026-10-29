-- GENERADO con tools/gen_migration.py a partir del SQL real del backend (inferencia de columnas/tipos + claves ON CONFLICT).
-- Tipos por convención de nombre/CAST; restricciones de negocio finas (CHECK/FK) se endurecen módulo a módulo.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE OR REPLACE FUNCTION app_tenant() RETURNS uuid LANGUAGE sql STABLE AS $$ SELECT NULLIF(current_setting('app.current_tenant_id', true), '')::uuid $$;

CREATE TABLE IF NOT EXISTS agent_executions (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  action text,
  agent text,
  completed_at timestamptz,
  error_code text,
  execution_id uuid,
  input_hash text,
  policy_reason text,
  request_id uuid,
  requires_human_review boolean,
  result jsonb,
  started_at timestamptz,
  status text,
  tenant_id uuid NOT NULL,
  tool_calls jsonb,
  trace_id uuid,
  warnings jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_agent_executions_tenant ON agent_executions(tenant_id);
CREATE TABLE IF NOT EXISTS agent_memories (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent text,
  confidence numeric(20,6),
  content jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz,
  memory_id uuid,
  source text,
  tenant_id uuid NOT NULL,
  version integer
);
CREATE INDEX IF NOT EXISTS ix_agent_memories_tenant ON agent_memories(tenant_id);
CREATE TABLE IF NOT EXISTS agent_memory_records (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent text,
  content jsonb,
  content_hash text,
  created_at timestamptz NOT NULL DEFAULT now(),
  embedding jsonb,
  expires_at timestamptz,
  importance integer,
  memory_id uuid,
  memory_type text,
  scope text,
  source text,
  subject_key text,
  tenant_id uuid NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, agent, content_hash)
);
CREATE INDEX IF NOT EXISTS ix_agent_memory_records_tenant ON agent_memory_records(tenant_id);
CREATE TABLE IF NOT EXISTS agent_neural_invocations (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent text,
  confidence numeric(20,6),
  decision text,
  input_hash text,
  model_id uuid,
  node_id uuid,
  output_hash text,
  purpose text,
  reason text,
  request_id text,
  status text,
  tenant_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, request_id)
);
CREATE INDEX IF NOT EXISTS ix_agent_neural_invocations_tenant ON agent_neural_invocations(tenant_id);
CREATE TABLE IF NOT EXISTS agent_neural_policies (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent text,
  allowed_decisions text[],
  enabled boolean,
  environment text,
  min_confidence numeric(20,6),
  model_id uuid,
  policy_id uuid,
  purpose text,
  tenant_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, agent, purpose, environment)
);
CREATE INDEX IF NOT EXISTS ix_agent_neural_policies_tenant ON agent_neural_policies(tenant_id);
CREATE TABLE IF NOT EXISTS agent_tool_executions (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  action text,
  agent text,
  approval_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  error_code text,
  execution_id uuid,
  input_hash text,
  payload jsonb,
  request_id uuid,
  requested_by text,
  requires_human_approval boolean,
  result jsonb,
  status text,
  tenant_id uuid NOT NULL,
  tool_name text,
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_agent_tool_executions_tenant ON agent_tool_executions(tenant_id);
CREATE TABLE IF NOT EXISTS agent_tool_policies (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  allowed_actions jsonb,
  allowed_agents jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  enabled boolean,
  max_payload_bytes integer,
  policy_id uuid,
  requires_human_approval boolean,
  risk_level text,
  tenant_id uuid NOT NULL,
  tool_name text,
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, tool_name)
);
CREATE INDEX IF NOT EXISTS ix_agent_tool_policies_tenant ON agent_tool_policies(tenant_id);
CREATE TABLE IF NOT EXISTS agent_workflow_approvals (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  approval_id uuid,
  approved_by uuid,
  decision text,
  execution_id uuid,
  reason text,
  tenant_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_agent_workflow_approvals_tenant ON agent_workflow_approvals(tenant_id);
CREATE TABLE IF NOT EXISTS autonomous_operations (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  execution_id uuid,
  operation_id uuid,
  state text,
  tenant_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_autonomous_operations_tenant ON autonomous_operations(tenant_id);
CREATE TABLE IF NOT EXISTS clinical_allergies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id uuid,
  reaction text,
  recorded_by uuid,
  severity text,
  status text NOT NULL DEFAULT 'ACTIVE',
  substance_code text,
  substance_name text,
  tenant_id uuid NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_clinical_allergies_tenant ON clinical_allergies(tenant_id);
CREATE TABLE IF NOT EXISTS clinical_care_plans (
  created_by uuid,
  encounter_id uuid,
  goals text,
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  interventions text,
  patient_id uuid,
  start_date date,
  target_date date,
  tenant_id uuid NOT NULL,
  title text
);
CREATE INDEX IF NOT EXISTS ix_clinical_care_plans_tenant ON clinical_care_plans(tenant_id);
CREATE TABLE IF NOT EXISTS clinical_diagnoses (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code text,
  created_by uuid,
  description text,
  encounter_id uuid,
  is_primary boolean,
  tenant_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_clinical_diagnoses_tenant ON clinical_diagnoses(tenant_id);
CREATE TABLE IF NOT EXISTS clinical_encounters (
  completed_at timestamptz,
  created_by uuid,
  encounter_type text,
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id uuid,
  practitioner_id uuid,
  started_at timestamptz,
  state text,
  tenant_id uuid NOT NULL,
  updated_by uuid
);
CREATE INDEX IF NOT EXISTS ix_clinical_encounters_tenant ON clinical_encounters(tenant_id);
CREATE TABLE IF NOT EXISTS clinical_imaging_orders (
  encounter_id uuid,
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  indication text,
  modality text,
  ordered_by uuid,
  priority text,
  report_text text,
  reported_at timestamptz,
  reported_by uuid,
  status text,
  study_code text,
  study_name text,
  tenant_id uuid NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_clinical_imaging_orders_tenant ON clinical_imaging_orders(tenant_id);
CREATE TABLE IF NOT EXISTS clinical_lab_orders (
  clinical_question text,
  encounter_id uuid,
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ordered_by uuid,
  priority text,
  result_at timestamptz,
  result_by uuid,
  result_text text,
  status text,
  tenant_id uuid NOT NULL,
  test_code text,
  test_name text
);
CREATE INDEX IF NOT EXISTS ix_clinical_lab_orders_tenant ON clinical_lab_orders(tenant_id);
CREATE TABLE IF NOT EXISTS clinical_medication_orders (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_by uuid,
  dose numeric(20,6),
  dose_unit text,
  encounter_id uuid,
  end_date date,
  frequency text,
  medication_code text,
  medication_name text,
  route text,
  start_date date,
  tenant_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_clinical_medication_orders_tenant ON clinical_medication_orders(tenant_id);
CREATE TABLE IF NOT EXISTS clinical_notes (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_by uuid,
  encounter_id uuid,
  note_text text,
  tenant_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_clinical_notes_tenant ON clinical_notes(tenant_id);
CREATE TABLE IF NOT EXISTS clinical_patients (
  birth_date date,
  created_by uuid,
  document_number text,
  document_type text,
  family_name text,
  given_name text,
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sex_at_birth text,
  tenant_id uuid NOT NULL,
  UNIQUE (tenant_id, document_type, document_number)
);
CREATE INDEX IF NOT EXISTS ix_clinical_patients_tenant ON clinical_patients(tenant_id);
CREATE TABLE IF NOT EXISTS clinical_vitals (
  diastolic_bp numeric(20,6),
  encounter_id uuid,
  heart_rate numeric(20,6),
  height_cm numeric(20,6),
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  measured_at timestamptz,
  oxygen_saturation numeric(20,6),
  recorded_by uuid,
  respiratory_rate numeric(20,6),
  systolic_bp numeric(20,6),
  temperature_c numeric(20,6),
  tenant_id uuid NOT NULL,
  weight_kg numeric(20,6)
);
CREATE INDEX IF NOT EXISTS ix_clinical_vitals_tenant ON clinical_vitals(tenant_id);
CREATE TABLE IF NOT EXISTS d (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  issue_date date,
  tenant_id uuid NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_d_tenant ON d(tenant_id);
CREATE TABLE IF NOT EXISTS edge_attestations (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  attestation_id uuid,
  boot_id text,
  device_id uuid,
  failure_reason text,
  firmware_hash text,
  measurement_hash text,
  nonce text,
  signature text,
  tenant_id uuid NOT NULL,
  verified boolean,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_edge_attestations_tenant ON edge_attestations(tenant_id);
CREATE TABLE IF NOT EXISTS edge_chaos_runs (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  chaos_run_id uuid,
  completed_at timestamptz,
  evidence jsonb,
  observed_safe_state boolean,
  scenario text,
  seed integer,
  started_at timestamptz,
  status text,
  target_device_id uuid,
  tenant_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_edge_chaos_runs_tenant ON edge_chaos_runs(tenant_id);
CREATE TABLE IF NOT EXISTS edge_commands (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  acknowledged_at timestamptz,
  command_id uuid,
  command_type text,
  completed_at timestamptz,
  device_id uuid,
  envelope jsonb,
  expires_at timestamptz,
  lease_expires_at timestamptz,
  lease_id uuid,
  nonce text,
  operation_id uuid,
  payload jsonb,
  payload_hash text,
  result jsonb,
  sequence bigint,
  signature text,
  status text NOT NULL DEFAULT 'issued',
  tenant_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_edge_commands_tenant ON edge_commands(tenant_id);
CREATE TABLE IF NOT EXISTS edge_device_credentials (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  algorithm text,
  device_id uuid,
  fingerprint text,
  public_key text,
  status text NOT NULL DEFAULT 'active',
  tenant_id uuid NOT NULL,
  valid_from date,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_edge_device_credentials_tenant ON edge_device_credentials(tenant_id);
CREATE TABLE IF NOT EXISTS edge_devices (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  capabilities jsonb,
  device_id uuid,
  device_type text,
  key_fingerprint text,
  key_ref text,
  last_heartbeat_at timestamptz,
  last_sequence bigint NOT NULL DEFAULT 0,
  name text,
  node_id uuid,
  safety_state text NOT NULL DEFAULT 'safe',
  status text NOT NULL DEFAULT 'registered',
  tenant_id uuid NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_edge_devices_tenant ON edge_devices(tenant_id);
CREATE TABLE IF NOT EXISTS edge_event_spool (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id uuid,
  event_key text,
  event_type text,
  payload jsonb,
  payload_hash text,
  sequence bigint,
  status text,
  tenant_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, device_id, sequence)
);
CREATE INDEX IF NOT EXISTS ix_edge_event_spool_tenant ON edge_event_spool(tenant_id);
CREATE TABLE IF NOT EXISTS edge_firmware_artifacts (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  artifact_id uuid,
  artifact_uri text,
  manifest jsonb,
  platform text,
  sha256 text,
  signature text,
  status text NOT NULL DEFAULT 'published',
  tenant_id uuid NOT NULL,
  version text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_edge_firmware_artifacts_tenant ON edge_firmware_artifacts(tenant_id);
CREATE TABLE IF NOT EXISTS edge_heartbeats (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  connectivity jsonb,
  device_id uuid,
  firmware_version text,
  health jsonb,
  safety_state text,
  sequence bigint,
  signature text,
  tenant_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, device_id, sequence)
);
CREATE INDEX IF NOT EXISTS ix_edge_heartbeats_tenant ON edge_heartbeats(tenant_id);
CREATE TABLE IF NOT EXISTS edge_mesh_links (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  child_device_id uuid,
  last_seen_at timestamptz,
  latency_ms numeric(20,6),
  packet_loss numeric(20,6),
  parent_device_id uuid,
  priority integer,
  status text,
  tenant_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, parent_device_id, child_device_id)
);
CREATE INDEX IF NOT EXISTS ix_edge_mesh_links_tenant ON edge_mesh_links(tenant_id);
CREATE TABLE IF NOT EXISTS edge_ota_deployments (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  artifact_id uuid,
  deployment_id uuid,
  device_id uuid,
  manifest_hash text,
  ring text,
  target_version text,
  tenant_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_edge_ota_deployments_tenant ON edge_ota_deployments(tenant_id);
CREATE TABLE IF NOT EXISTS edge_reconciliation_runs (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  completed_at timestamptz,
  conflict_count integer,
  device_id uuid,
  duplicate_count integer,
  evidence jsonb,
  last_device_sequence integer,
  last_server_sequence integer,
  missing_count integer,
  reconciliation_id uuid,
  status text,
  tenant_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_edge_reconciliation_runs_tenant ON edge_reconciliation_runs(tenant_id);
CREATE TABLE IF NOT EXISTS edge_rollout_policies (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  enabled boolean,
  max_concurrent integer,
  max_failure_percent numeric(20,6),
  min_healthy_percent numeric(20,6),
  platform text,
  require_attestation boolean,
  require_rollback_artifact boolean,
  ring text,
  tenant_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, platform, ring)
);
CREATE INDEX IF NOT EXISTS ix_edge_rollout_policies_tenant ON edge_rollout_policies(tenant_id);
CREATE TABLE IF NOT EXISTS edge_safety_events (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  action text,
  actor text,
  device_id uuid,
  new_state text,
  previous_state text,
  reason text,
  tenant_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_edge_safety_events_tenant ON edge_safety_events(tenant_id);
CREATE TABLE IF NOT EXISTS edge_transport_replays (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id uuid,
  nonce text,
  payload_hash text,
  sequence bigint,
  tenant_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_edge_transport_replays_tenant ON edge_transport_replays(tenant_id);
CREATE TABLE IF NOT EXISTS edge_watchdog_events (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  action text,
  device_id uuid,
  last_heartbeat_at timestamptz,
  new_state text,
  previous_state text,
  reason text,
  tenant_id uuid NOT NULL,
  timeout_seconds integer,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_edge_watchdog_events_tenant ON edge_watchdog_events(tenant_id);
CREATE TABLE IF NOT EXISTS inventory_items (
  active boolean,
  created_by uuid,
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text,
  sku text,
  tenant_id uuid NOT NULL,
  unit text
);
CREATE INDEX IF NOT EXISTS ix_inventory_items_tenant ON inventory_items(tenant_id);
CREATE TABLE IF NOT EXISTS inventory_movements (
  balance_after numeric(20,6),
  created_by uuid,
  direction text,
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  idempotency_key text,
  item_id uuid,
  quantity numeric(20,6),
  reason text,
  reference text,
  tenant_id uuid NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_inventory_movements_tenant ON inventory_movements(tenant_id);
CREATE TABLE IF NOT EXISTS inventory_stock (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  item_id uuid,
  quantity numeric(20,6),
  tenant_id uuid NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_inventory_stock_tenant ON inventory_stock(tenant_id);
CREATE TABLE IF NOT EXISTS ml_dataset_snapshots (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  content_hash text,
  dataset_id uuid,
  feature_ids uuid[],
  name text,
  row_count integer,
  schema_hash text,
  source_query_hash text,
  split jsonb,
  tenant_id uuid NOT NULL,
  version text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, name, version)
);
CREATE INDEX IF NOT EXISTS ix_ml_dataset_snapshots_tenant ON ml_dataset_snapshots(tenant_id);
CREATE TABLE IF NOT EXISTS ml_deployments (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  deployment_id uuid,
  environment text,
  model_id uuid,
  reason text,
  rollout_percent numeric(20,6),
  state text,
  tenant_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_ml_deployments_tenant ON ml_deployments(tenant_id);
CREATE TABLE IF NOT EXISTS ml_drift_metrics (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  action text,
  detected boolean,
  drift_id uuid,
  feature_name text,
  metric text,
  model_id uuid,
  tenant_id uuid NOT NULL,
  threshold numeric(20,6),
  value numeric(20,6),
  window_end timestamptz,
  window_start timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_ml_drift_metrics_tenant ON ml_drift_metrics(tenant_id);
CREATE TABLE IF NOT EXISTS ml_feature_definitions (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  data_type text,
  definition jsonb,
  feature_id uuid,
  name text,
  source text,
  status text,
  tenant_id uuid NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  version text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, name, version)
);
CREATE INDEX IF NOT EXISTS ix_ml_feature_definitions_tenant ON ml_feature_definitions(tenant_id);
CREATE TABLE IF NOT EXISTS ml_feature_observations (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  feature_name text,
  feature_version text,
  node_id uuid,
  observation_id uuid,
  observed_at timestamptz,
  quality text,
  source text,
  tenant_id uuid NOT NULL,
  value_double numeric(20,6),
  window_end text,
  window_start text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_ml_feature_observations_tenant ON ml_feature_observations(tenant_id);
CREATE TABLE IF NOT EXISTS ml_inference_routes (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  active boolean NOT NULL DEFAULT true,
  environment text,
  model_id uuid,
  tenant_id uuid NOT NULL,
  traffic_percent numeric(20,6),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, model_id, environment)
);
CREATE INDEX IF NOT EXISTS ix_ml_inference_routes_tenant ON ml_inference_routes(tenant_id);
CREATE TABLE IF NOT EXISTS ml_model_evaluations (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  evaluation_id uuid,
  evaluator text,
  gate text,
  metrics jsonb,
  model_id uuid,
  passed boolean,
  tenant_id uuid NOT NULL,
  training_id uuid,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_ml_model_evaluations_tenant ON ml_model_evaluations(tenant_id);
CREATE TABLE IF NOT EXISTS ml_training_runs (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  algorithm text,
  candidate_version text,
  dataset_id uuid,
  framework text,
  hyperparameters jsonb,
  model_name text,
  tenant_id uuid NOT NULL,
  training_id uuid,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_ml_training_runs_tenant ON ml_training_runs(tenant_id);
CREATE TABLE IF NOT EXISTS neural_inference_audit (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent text,
  confidence numeric(20,6),
  error_code text,
  inference_id uuid,
  input_hash text,
  latency_ms integer,
  model_id uuid,
  output jsonb,
  output_hash text,
  request_id uuid,
  status text,
  subject_key text,
  tenant_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, request_id)
);
CREATE INDEX IF NOT EXISTS ix_neural_inference_audit_tenant ON neural_inference_audit(tenant_id);
CREATE TABLE IF NOT EXISTS neural_model_registry (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  approved_for_inference boolean,
  artifact_uri text,
  created_at timestamptz NOT NULL DEFAULT now(),
  format text,
  framework text,
  input_schema jsonb,
  model_id uuid,
  name text,
  output_schema jsonb,
  sha256 text,
  status text,
  tenant_id uuid,
  updated_at timestamptz NOT NULL DEFAULT now(),
  version text,
  UNIQUE (tenant_id, name, version)
);
CREATE INDEX IF NOT EXISTS ix_neural_model_registry_tenant ON neural_model_registry(tenant_id);
CREATE TABLE IF NOT EXISTS sales_order_lines (
  billing_account_id uuid,
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  item_id uuid,
  line_no integer,
  quantity numeric(20,6),
  sales_order_id uuid,
  subtotal numeric(20,6),
  taxes jsonb,
  tenant_id uuid NOT NULL,
  unit_price numeric(20,6)
);
CREATE INDEX IF NOT EXISTS ix_sales_order_lines_tenant ON sales_order_lines(tenant_id);
CREATE TABLE IF NOT EXISTS sales_orders (
  billing_document_id uuid,
  created_by uuid,
  currency text,
  fulfilled_at timestamptz,
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_series text,
  partner_id uuid,
  payment_terms_days integer,
  status text,
  tenant_id uuid NOT NULL,
  total_amount numeric(20,6)
);
CREATE INDEX IF NOT EXISTS ix_sales_orders_tenant ON sales_orders(tenant_id);
CREATE TABLE IF NOT EXISTS sst_activities (
  activity_type text,
  aforo integer,
  asset_id uuid,
  contractor_id uuid,
  end_at timestamptz,
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  jurisdiction text,
  requester_id text,
  risk_level text,
  start_at timestamptz,
  status text NOT NULL DEFAULT 'draft',
  tenant_id uuid NOT NULL,
  timezone text,
  updated_at timestamptz NOT NULL DEFAULT now(),
  zone_id uuid
);
CREATE INDEX IF NOT EXISTS ix_sst_activities_tenant ON sst_activities(tenant_id);
CREATE TABLE IF NOT EXISTS sst_approval_tokens (
  action text,
  approval_id uuid,
  expires_at timestamptz,
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  recipient_id text,
  revoked boolean NOT NULL DEFAULT false,
  tenant_id uuid NOT NULL,
  token_hash text,
  used_at timestamptz,
  version integer
);
CREATE INDEX IF NOT EXISTS ix_sst_approval_tokens_tenant ON sst_approval_tokens(tenant_id);
CREATE TABLE IF NOT EXISTS sst_approvals (
  action text,
  activity_id uuid,
  approver_role text,
  backup_id text,
  conditions jsonb,
  decided_at timestamptz,
  decided_by uuid,
  expires_at timestamptz,
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  justification text,
  primary_id text,
  request_type text,
  requester_id text,
  requires_mfa boolean,
  risk_level text,
  status text NOT NULL DEFAULT 'pending',
  tenant_id uuid NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_sst_approvals_tenant ON sst_approvals(tenant_id);
CREATE TABLE IF NOT EXISTS sst_audit_chain (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at_iso text,
  event jsonb,
  hash text,
  prev_hash text,
  seq integer,
  tenant_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_sst_audit_chain_tenant ON sst_audit_chain(tenant_id);
CREATE TABLE IF NOT EXISTS sst_notification_attempts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  response jsonb,
  status text,
  tenant_id uuid NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_sst_notification_attempts_tenant ON sst_notification_attempts(tenant_id);
CREATE TABLE IF NOT EXISTS sst_requirement_evaluations (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  activity_id uuid,
  evaluated_at timestamptz,
  evidence_id uuid,
  mandatory boolean,
  reason text,
  requirement_key text,
  rule_id text,
  rule_version text,
  severity text,
  status text,
  tenant_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, activity_id, requirement_key)
);
CREATE INDEX IF NOT EXISTS ix_sst_requirement_evaluations_tenant ON sst_requirement_evaluations(tenant_id);
CREATE TABLE IF NOT EXISTS sst_temporary_assignments (
  activity_id uuid,
  asset_id uuid,
  end_at timestamptz,
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  inspection_id uuid,
  proposed_by text,
  responsible_id uuid,
  start_at timestamptz,
  status text NOT NULL DEFAULT 'proposed',
  tenant_id uuid NOT NULL,
  verified_by text,
  zone_id uuid
);
CREATE INDEX IF NOT EXISTS ix_sst_temporary_assignments_tenant ON sst_temporary_assignments(tenant_id);
CREATE TABLE IF NOT EXISTS sst_webhook_events (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id text,
  tenant_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_sst_webhook_events_tenant ON sst_webhook_events(tenant_id);
CREATE TABLE IF NOT EXISTS tables (
  row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  table_name text,
  table_schema jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

DO $$ DECLARE t text; BEGIN FOR t IN SELECT unnest(ARRAY['agent_executions','agent_memories','agent_memory_records','agent_neural_invocations','agent_neural_policies','agent_tool_executions','agent_tool_policies','agent_workflow_approvals','autonomous_operations','clinical_allergies','clinical_care_plans','clinical_diagnoses','clinical_encounters','clinical_imaging_orders','clinical_lab_orders','clinical_medication_orders','clinical_notes','clinical_patients','clinical_vitals','d','edge_attestations','edge_chaos_runs','edge_commands','edge_device_credentials','edge_devices','edge_event_spool','edge_firmware_artifacts','edge_heartbeats','edge_mesh_links','edge_ota_deployments','edge_reconciliation_runs','edge_rollout_policies','edge_safety_events','edge_transport_replays','edge_watchdog_events','inventory_items','inventory_movements','inventory_stock','ml_dataset_snapshots','ml_deployments','ml_drift_metrics','ml_feature_definitions','ml_feature_observations','ml_inference_routes','ml_model_evaluations','ml_training_runs','neural_inference_audit','sales_order_lines','sales_orders','sst_activities','sst_approval_tokens','sst_approvals','sst_audit_chain','sst_notification_attempts','sst_requirement_evaluations','sst_temporary_assignments','sst_webhook_events']) LOOP
  EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t); EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
  EXECUTE format('DROP POLICY IF EXISTS %I ON %I', t||'_tenant_isolation', t);
  EXECUTE format('CREATE POLICY %I ON %I USING (tenant_id = app_tenant()) WITH CHECK (tenant_id = app_tenant())', t||'_tenant_isolation', t);
END LOOP; END $$;
ALTER TABLE neural_model_registry ENABLE ROW LEVEL SECURITY; ALTER TABLE neural_model_registry FORCE ROW LEVEL SECURITY; DROP POLICY IF EXISTS neural_model_registry_tenant_isolation ON neural_model_registry;
CREATE POLICY neural_model_registry_tenant_isolation ON neural_model_registry USING (tenant_id IS NULL OR tenant_id = app_tenant()) WITH CHECK (tenant_id = app_tenant());  -- NULL = fila global (solo lectura para tenants)
