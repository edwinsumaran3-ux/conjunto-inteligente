-- 0006 · Ciclo de vida del incidente: línea de tiempo, vínculo con eventos y notificaciones.

ALTER TABLE incidents ADD COLUMN IF NOT EXISTS acknowledged_at  TIMESTAMPTZ;
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS acknowledged_by  TEXT;
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS resolved_at      TIMESTAMPTZ;
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS resolved_by      TEXT;
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS resolution_note  TEXT;

CREATE TABLE IF NOT EXISTS incident_events (
  incident_id UUID NOT NULL REFERENCES incidents(incident_id) ON DELETE RESTRICT,
  event_id    UUID NOT NULL REFERENCES events(event_id) ON DELETE RESTRICT,
  linked_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (incident_id, event_id)
);
CREATE INDEX IF NOT EXISTS ix_incident_events_event ON incident_events(event_id);

CREATE TABLE IF NOT EXISTS incident_timeline (
  entry_id    BIGSERIAL PRIMARY KEY,
  incident_id UUID NOT NULL REFERENCES incidents(incident_id) ON DELETE RESTRICT,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  entry_type  TEXT NOT NULL CHECK (entry_type IN ('EVENT','ACTION','APPROVAL','NOTE','STATUS','AI_ADVISORY','NOTIFICATION')),
  actor       TEXT NOT NULL DEFAULT 'system',
  summary     TEXT NOT NULL CHECK (length(summary) BETWEEN 1 AND 2000),
  details     JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_incident_timeline_incident ON incident_timeline(incident_id, occurred_at);

CREATE TABLE IF NOT EXISTS notifications (
  notification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       TEXT NOT NULL DEFAULT 'default',
  incident_id     UUID REFERENCES incidents(incident_id) ON DELETE SET NULL,
  channel         TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','SENT','FAILED')),
  attempts        INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  last_error      TEXT,
  payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  sent_at         TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_notifications_status ON notifications(status, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_notifications_incident ON notifications(incident_id);

-- Un incidente cerrado no se reabre en silencio.
CREATE OR REPLACE FUNCTION incident_status_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status IN ('CLOSED','FALSE_POSITIVE') AND NEW.status IS DISTINCT FROM OLD.status THEN
    RAISE EXCEPTION 'incidente % en estado terminal (%): no se puede cambiar a %', OLD.incident_id, OLD.status, NEW.status
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END
$$;
CREATE OR REPLACE TRIGGER trg_incident_status_guard BEFORE UPDATE OF status ON incidents
  FOR EACH ROW EXECUTE FUNCTION incident_status_guard();
