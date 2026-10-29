-- 0003 · Integridad: constraints, unicidad correcta e índices.
-- Las CHECK se añaden NOT VALID: se aplican a toda escritura nueva y se
-- validan sobre datos históricos en 0008 (con aviso, sin bloquear el despliegue).

-- BUG CORREGIDO: el edge-gateway emite eventos internos (SENSOR_FAIL,
-- DEVICE_DISCOVERED) con sequence_number=0. Con UNIQUE(device_id,sequence_number)
-- el segundo evento de un mismo dispositivo se descartaba en silencio
-- (ON CONFLICT DO NOTHING) y nunca llegaba a correlación. El firmware numera
-- desde 1, así que la unicidad solo tiene sentido para sequence_number > 0.
-- La idempotencia por event_id (PK) se mantiene intacta.
ALTER TABLE events DROP CONSTRAINT IF EXISTS events_device_id_sequence_number_key;
CREATE UNIQUE INDEX IF NOT EXISTS ux_events_device_seq ON events(device_id, sequence_number) WHERE sequence_number > 0;

SELECT vigia_add_constraint('events', 'ck_events_priority',
  $c$CHECK (priority IN ('CRITICAL','SECURITY','ANOMALY','TELEMETRY')) NOT VALID$c$);
SELECT vigia_add_constraint('events', 'ck_events_sequence_nonneg', $c$CHECK (sequence_number >= 0) NOT VALID$c$);
SELECT vigia_add_constraint('events', 'ck_events_device_len', $c$CHECK (length(device_id) BETWEEN 1 AND 128) NOT VALID$c$);
SELECT vigia_add_constraint('events', 'ck_events_payload_object', $c$CHECK (jsonb_typeof(payload) = 'object') NOT VALID$c$);
SELECT vigia_add_constraint('events', 'ck_events_payload_size', $c$CHECK (octet_length(payload::text) <= 65536) NOT VALID$c$);

SELECT vigia_add_constraint('incidents', 'ck_incidents_status',
  $c$CHECK (status IN ('OPEN','ACKNOWLEDGED','INVESTIGATING','RESOLVED','FALSE_POSITIVE','CLOSED')) NOT VALID$c$);
SELECT vigia_add_constraint('incidents', 'ck_incidents_severity',
  $c$CHECK (severity IN ('CRITICAL','SECURITY','ANOMALY','HIGH','MEDIUM','LOW')) NOT VALID$c$);

SELECT vigia_add_constraint('agent_actions', 'ck_agent_actions_severity',
  $c$CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')) NOT VALID$c$);
SELECT vigia_add_constraint('agent_actions', 'ck_agent_actions_type',
  $c$CHECK (action_type IN ('SOUND_ALARM','LOCK_ACCESS','UNLOCK_ACCESS','NOTIFY_AUTHORITIES','FOCUS_CAMERA','START_RECORDING','SAFE_HOLD','NO_OP')) NOT VALID$c$);
SELECT vigia_add_constraint('agent_actions', 'ck_agent_actions_status',
  $c$CHECK (status ~ '^[A-Z_]+(:.*)?$') NOT VALID$c$);
SELECT vigia_add_constraint('agent_actions', 'ck_agent_actions_payload_object', $c$CHECK (jsonb_typeof(payload) = 'object') NOT VALID$c$);

SELECT vigia_add_constraint('agent_approvals', 'ck_agent_approvals_decision',
  $c$CHECK (decision IN ('PENDING','APPROVED','REJECTED','EXPIRED')) NOT VALID$c$);
SELECT vigia_add_constraint('agent_approvals', 'ck_agent_approvals_window', $c$CHECK (expires_at > requested_at) NOT VALID$c$);
SELECT vigia_add_constraint('agent_approvals', 'ck_agent_approvals_decided',
  $c$CHECK (decision NOT IN ('APPROVED','REJECTED') OR (decided_by IS NOT NULL AND decided_at IS NOT NULL)) NOT VALID$c$);
SELECT vigia_add_constraint('agent_approvals', 'ck_agent_approvals_fallback',
  $c$CHECK (fallback_action IN ('SAFE_HOLD','NO_OP','SOUND_ALARM','NOTIFY_AUTHORITIES')) NOT VALID$c$);

SELECT vigia_add_constraint('devices', 'ck_devices_id_len', $c$CHECK (length(device_id) BETWEEN 1 AND 128) NOT VALID$c$);
SELECT vigia_add_constraint('camera_channels', 'ck_camera_channels_protocol',
  $c$CHECK (protocol IN ('RTSP','RTMP','SRT','ONVIF','HLS','WEBRTC','HTTP_MJPEG')) NOT VALID$c$);

-- Índices de acceso real (barrido de aprobaciones, dashboard, correlación).
CREATE INDEX IF NOT EXISTS brin_events_ts           ON events USING brin(ts);
CREATE INDEX IF NOT EXISTS ix_events_type_ts        ON events(type, ts DESC);
CREATE INDEX IF NOT EXISTS ix_device_events_device  ON device_events(device_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_device_events_event   ON device_events(event_id);
CREATE INDEX IF NOT EXISTS ix_agent_actions_incident ON agent_actions(incident_id);
CREATE INDEX IF NOT EXISTS ix_agent_actions_target   ON agent_actions(target_device_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_agent_approvals_action ON agent_approvals(action_id);
CREATE INDEX IF NOT EXISTS ix_agent_approvals_pending ON agent_approvals(expires_at) WHERE decision = 'PENDING';
CREATE INDEX IF NOT EXISTS ix_incidents_severity     ON incidents(severity, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_incidents_open         ON incidents(created_at DESC) WHERE status = 'OPEN';
CREATE INDEX IF NOT EXISTS ix_devices_last_seen      ON devices(last_seen DESC);
CREATE INDEX IF NOT EXISTS ix_devices_unhealthy      ON devices(device_id) WHERE NOT healthy;

-- Un evento no debe proyectarse dos veces al mismo dispositivo/tipo.
-- Si ya existen duplicados históricos no se bloquea el despliegue: se avisa.
DO $$
BEGIN
  CREATE UNIQUE INDEX IF NOT EXISTS ux_device_events_event_kind ON device_events(event_id, kind);
EXCEPTION WHEN unique_violation THEN
  RAISE WARNING 'ux_device_events_event_kind no creado: existen duplicados historicos en device_events';
END
$$;
