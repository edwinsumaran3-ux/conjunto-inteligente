CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE IF NOT EXISTS events (
 event_id UUID PRIMARY KEY, device_id TEXT NOT NULL, zone TEXT, type TEXT NOT NULL, priority TEXT NOT NULL,
 sequence_number BIGINT NOT NULL, ts TIMESTAMPTZ NOT NULL, payload JSONB NOT NULL DEFAULT '{}'::jsonb,
 signature TEXT, received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(device_id, sequence_number)
);
CREATE INDEX IF NOT EXISTS idx_events_device_ts ON events(device_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_events_priority_ts ON events(priority, ts DESC);
CREATE TABLE IF NOT EXISTS incidents (
 incident_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), correlation_key TEXT UNIQUE NOT NULL,
 severity TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'OPEN', created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), details JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_incidents_status_created ON incidents(status, created_at DESC);
CREATE TABLE IF NOT EXISTS devices (
 device_id TEXT PRIMARY KEY, zone TEXT, fw_version TEXT, last_seen TIMESTAMPTZ,
 healthy BOOLEAN NOT NULL DEFAULT TRUE, metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS device_events (
 id BIGSERIAL PRIMARY KEY, device_id TEXT NOT NULL REFERENCES devices(device_id),
 event_id UUID NOT NULL REFERENCES events(event_id), kind TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE OR REPLACE VIEW dashboard_health AS
SELECT count(*) FILTER (WHERE healthy) AS healthy_devices, count(*) FILTER (WHERE NOT healthy) AS unhealthy_devices FROM devices;

-- Agent Orchestrator: propuestas de acción generadas por el loop Sense/Plan/Act/Reflect
CREATE TABLE IF NOT EXISTS agent_actions (
 action_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), incident_id UUID REFERENCES incidents(incident_id),
 agent_name TEXT NOT NULL, action_type TEXT NOT NULL, severity TEXT NOT NULL,
 target_device_id TEXT, zone TEXT, rationale TEXT NOT NULL, payload JSONB NOT NULL DEFAULT '{}'::jsonb,
 status TEXT NOT NULL DEFAULT 'PROPOSED', created_at TIMESTAMPTZ NOT NULL DEFAULT now(), resolved_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_agent_actions_status ON agent_actions(status, created_at DESC);

-- Human-in-the-loop: cola de aprobación para acciones CRITICAL/HIGH con firma criptográfica del operador
CREATE TABLE IF NOT EXISTS agent_approvals (
 approval_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), action_id UUID NOT NULL REFERENCES agent_actions(action_id),
 requested_at TIMESTAMPTZ NOT NULL DEFAULT now(), expires_at TIMESTAMPTZ NOT NULL,
 decision TEXT NOT NULL DEFAULT 'PENDING', decided_by TEXT, decided_at TIMESTAMPTZ,
 operator_signature TEXT, fallback_action TEXT NOT NULL DEFAULT 'SAFE_HOLD'
);
CREATE INDEX IF NOT EXISTS idx_agent_approvals_decision ON agent_approvals(decision, requested_at DESC);

-- Inventario de equipos detectados automáticamente (cámaras, sensores IR/láser, gateways) con marca/modelo/compatibilidad
CREATE TABLE IF NOT EXISTS discovered_devices (
 device_id TEXT PRIMARY KEY, device_class TEXT NOT NULL, vendor TEXT, model TEXT, firmware_hint TEXT,
 protocol TEXT NOT NULL, address TEXT NOT NULL, compatibility TEXT NOT NULL DEFAULT 'UNKNOWN',
 auto_connected BOOLEAN NOT NULL DEFAULT FALSE, zone TEXT, first_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
 last_seen TIMESTAMPTZ NOT NULL DEFAULT now(), metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_discovered_devices_class ON discovered_devices(device_class, last_seen DESC);

-- Registro de canales de cámara (1-24) para el grid del dashboard y su estado de streaming
CREATE TABLE IF NOT EXISTS camera_channels (
 channel_id TEXT PRIMARY KEY, slot INTEGER NOT NULL CHECK (slot BETWEEN 1 AND 24), zone TEXT,
 stream_url TEXT, protocol TEXT NOT NULL DEFAULT 'RTSP', ptz_capable BOOLEAN NOT NULL DEFAULT FALSE,
 audio_capable BOOLEAN NOT NULL DEFAULT FALSE, vendor TEXT, model TEXT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(slot)
);


-- Neural Control Plane: audit of advisory inference, never an authority for physical actions
CREATE TABLE IF NOT EXISTS neural_inference_audit (
 request_id UUID PRIMARY KEY, tenant_id TEXT NOT NULL, purpose TEXT NOT NULL, provider TEXT, model TEXT,
 status TEXT NOT NULL, advisory_only BOOLEAN NOT NULL DEFAULT TRUE, prompt_fingerprint TEXT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), latency_ms INTEGER, blocked_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_neural_audit_tenant_created ON neural_inference_audit(tenant_id, created_at DESC);
