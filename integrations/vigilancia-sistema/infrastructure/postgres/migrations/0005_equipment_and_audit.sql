-- 0005 · Registro persistente de equipo físico, journal de comandos blindado y auditoría inmutable.

-- Los SECRETOS HMAC nunca se guardan aquí: solo el identificador (key_id) que apunta al gestor de secretos.
CREATE TABLE IF NOT EXISTS equipment (
  equipment_id         TEXT PRIMARY KEY CHECK (equipment_id ~ '^[A-Za-z0-9][A-Za-z0-9_.-]{0,126}$'),
  tenant_id            TEXT NOT NULL DEFAULT 'default' REFERENCES tenants(tenant_id),
  equipment_type       TEXT NOT NULL CHECK (equipment_type IN ('DRONE','PTZ_CAMERA','GROUND_ROBOT','IR_ACTUATOR')),
  vendor               TEXT,
  model                TEXT,
  adapter              TEXT NOT NULL DEFAULT 'boundary',
  transport_configured BOOLEAN NOT NULL DEFAULT FALSE,
  enabled              BOOLEAN NOT NULL DEFAULT TRUE,
  key_id               TEXT,
  zone                 TEXT,
  metadata             JSONB NOT NULL DEFAULT '{}'::jsonb,
  registered_by        TEXT NOT NULL DEFAULT 'system',
  registered_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Un equipo no puede declararse con transporte real sin identidad criptográfica.
  CONSTRAINT ck_equipment_transport_requires_key CHECK (NOT transport_configured OR key_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS ix_equipment_tenant_type ON equipment(tenant_id, equipment_type);
CREATE OR REPLACE TRIGGER trg_equipment_touch BEFORE UPDATE ON equipment FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- Misma forma que crea CommandJournal.ensure_schema() en tiempo de ejecución (IF NOT EXISTS: ambos coexisten).
CREATE TABLE IF NOT EXISTS equipment_command_journal (
  command_id     UUID PRIMARY KEY,
  equipment_id   TEXT NOT NULL,
  equipment_type TEXT NOT NULL,
  action         TEXT NOT NULL,
  issued_by      TEXT NOT NULL,
  nonce          TEXT NOT NULL UNIQUE,
  issued_at      DOUBLE PRECISION NOT NULL,
  expires_at     DOUBLE PRECISION NOT NULL,
  status         TEXT NOT NULL,
  reason         TEXT,
  request        JSONB NOT NULL,
  response       JSONB,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_equipment_command_journal_device_created ON equipment_command_journal(equipment_id, created_at DESC);
ALTER TABLE equipment_command_journal ADD COLUMN IF NOT EXISTS tenant_id      TEXT NOT NULL DEFAULT 'default';
ALTER TABLE equipment_command_journal ADD COLUMN IF NOT EXISTS correlation_id TEXT;
CREATE INDEX IF NOT EXISTS ix_command_journal_status ON equipment_command_journal(status, created_at DESC);
-- Comandos que quedaron en RECEIVED (proceso caído a mitad): consultables para conciliación.
CREATE INDEX IF NOT EXISTS ix_command_journal_stuck ON equipment_command_journal(created_at) WHERE status = 'RECEIVED';

SELECT vigia_add_constraint('equipment_command_journal', 'ck_command_journal_window', $c$CHECK (expires_at >= issued_at) NOT VALID$c$);
SELECT vigia_add_constraint('equipment_command_journal', 'ck_command_journal_status', $c$CHECK (length(status) > 0) NOT VALID$c$);

-- El journal es evidencia: nada se borra, una vez resuelto no cambia, y los campos de la solicitud son inmutables.
CREATE OR REPLACE FUNCTION command_journal_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'equipment_command_journal es append-only: DELETE no permitido' USING ERRCODE = 'insufficient_privilege';
  END IF;
  IF OLD.status <> 'RECEIVED' THEN
    RAISE EXCEPTION 'comando % ya resuelto (%): no modificable', OLD.command_id, OLD.status USING ERRCODE = 'insufficient_privilege';
  END IF;
  IF NEW.command_id IS DISTINCT FROM OLD.command_id OR NEW.equipment_id IS DISTINCT FROM OLD.equipment_id
     OR NEW.equipment_type IS DISTINCT FROM OLD.equipment_type OR NEW.action IS DISTINCT FROM OLD.action
     OR NEW.issued_by IS DISTINCT FROM OLD.issued_by OR NEW.nonce IS DISTINCT FROM OLD.nonce
     OR NEW.issued_at IS DISTINCT FROM OLD.issued_at OR NEW.expires_at IS DISTINCT FROM OLD.expires_at
     OR NEW.request IS DISTINCT FROM OLD.request THEN
    RAISE EXCEPTION 'campos de la solicitud del comando % son inmutables', OLD.command_id USING ERRCODE = 'insufficient_privilege';
  END IF;
  RETURN NEW;
END
$$;
CREATE OR REPLACE TRIGGER trg_command_journal_guard BEFORE UPDATE OR DELETE ON equipment_command_journal
  FOR EACH ROW EXECUTE FUNCTION command_journal_guard();

CREATE OR REPLACE FUNCTION block_truncate() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'TRUNCATE no permitido sobre %', TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege';
END
$$;
CREATE OR REPLACE TRIGGER trg_command_journal_no_truncate BEFORE TRUNCATE ON equipment_command_journal
  FOR EACH STATEMENT EXECUTE FUNCTION block_truncate();

-- Auditoría append-only con cadena de hash (detecta borrado/alteración de filas intermedias).
CREATE TABLE IF NOT EXISTS audit_log (
  audit_id       BIGSERIAL PRIMARY KEY,
  tenant_id      TEXT NOT NULL DEFAULT 'default',
  occurred_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  actor          TEXT NOT NULL,
  actor_type     TEXT NOT NULL CHECK (actor_type IN ('OPERATOR','AGENT','SYSTEM','DEVICE','LLM')),
  action         TEXT NOT NULL,
  entity_type    TEXT,
  entity_id      TEXT,
  correlation_id TEXT,
  details        JSONB NOT NULL DEFAULT '{}'::jsonb,
  prev_hash      BYTEA,
  row_hash       BYTEA NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_audit_log_entity ON audit_log(entity_type, entity_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_audit_log_actor ON audit_log(actor, occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_audit_log_tenant_time ON audit_log(tenant_id, occurred_at DESC);

CREATE OR REPLACE FUNCTION audit_log_chain() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  v_prev BYTEA;
BEGIN
  PERFORM pg_advisory_xact_lock(727001);
  SELECT row_hash INTO v_prev FROM audit_log ORDER BY audit_id DESC LIMIT 1;
  NEW.prev_hash := v_prev;
  NEW.row_hash := digest(
    coalesce(v_prev, ''::bytea) || convert_to(concat_ws('|', NEW.tenant_id, NEW.occurred_at::text, NEW.actor, NEW.actor_type,
      NEW.action, coalesce(NEW.entity_type, ''), coalesce(NEW.entity_id, ''), coalesce(NEW.correlation_id, ''), NEW.details::text), 'UTF8'),
    'sha256');
  RETURN NEW;
END
$$;
CREATE OR REPLACE TRIGGER trg_audit_log_chain BEFORE INSERT ON audit_log FOR EACH ROW EXECUTE FUNCTION audit_log_chain();

CREATE OR REPLACE FUNCTION audit_log_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit_log es append-only' USING ERRCODE = 'insufficient_privilege';
END
$$;
CREATE OR REPLACE TRIGGER trg_audit_log_immutable BEFORE UPDATE OR DELETE ON audit_log FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();
CREATE OR REPLACE TRIGGER trg_audit_log_no_truncate BEFORE TRUNCATE ON audit_log FOR EACH STATEMENT EXECUTE FUNCTION block_truncate();

-- Devuelve el primer audit_id cuya prev_hash no enlaza con la fila anterior (NULL = cadena íntegra).
CREATE OR REPLACE FUNCTION verify_audit_chain() RETURNS BIGINT LANGUAGE sql STABLE AS $$
  SELECT audit_id FROM (
    SELECT audit_id, prev_hash, lag(row_hash) OVER (ORDER BY audit_id) AS expected_prev FROM audit_log
  ) t
  WHERE prev_hash IS DISTINCT FROM expected_prev
  ORDER BY audit_id LIMIT 1
$$;

-- Operadores: base para sustituir el token único por identidad individual con rol.
CREATE TABLE IF NOT EXISTS operators (
  operator_id  TEXT PRIMARY KEY CHECK (length(operator_id) BETWEEN 1 AND 128),
  tenant_id    TEXT NOT NULL DEFAULT 'default' REFERENCES tenants(tenant_id),
  display_name TEXT NOT NULL,
  role         TEXT NOT NULL CHECK (role IN ('VIEWER','OPERATOR','SUPERVISOR','ADMIN')),
  public_key   TEXT,
  active       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_operators_tenant_role ON operators(tenant_id, role) WHERE active;
CREATE OR REPLACE TRIGGER trg_operators_touch BEFORE UPDATE ON operators FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
