-- 0002 · Tenancy, sitios, zonas y utilidades comunes.
-- Aditiva: no elimina ni renombra nada de 0001. Los datos existentes
-- quedan asignados al tenant 'default'.

CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END
$$;

-- Helper idempotente: añade una constraint solo si no existe todavía.
CREATE OR REPLACE FUNCTION vigia_add_constraint(p_table regclass, p_name text, p_definition text)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = p_name AND conrelid = p_table) THEN
    EXECUTE format('ALTER TABLE %s ADD CONSTRAINT %I %s', p_table, p_name, p_definition);
  END IF;
END
$$;

CREATE TABLE IF NOT EXISTS tenants (
  tenant_id  TEXT PRIMARY KEY CHECK (tenant_id ~ '^[a-z0-9][a-z0-9_-]{0,62}$'),
  name       TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
  active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO tenants(tenant_id, name) VALUES ('default', 'Default tenant') ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS sites (
  site_id    TEXT PRIMARY KEY CHECK (site_id ~ '^[a-z0-9][a-z0-9_-]{0,62}$'),
  tenant_id  TEXT NOT NULL REFERENCES tenants(tenant_id),
  name       TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
  time_zone  TEXT NOT NULL DEFAULT 'America/Bogota',
  address    TEXT,
  active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_sites_tenant ON sites(tenant_id);

CREATE TABLE IF NOT EXISTS zones (
  zone_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id  TEXT NOT NULL REFERENCES tenants(tenant_id),
  site_id    TEXT NOT NULL REFERENCES sites(site_id),
  code       TEXT NOT NULL CHECK (length(code) BETWEEN 1 AND 128),
  name       TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
  kind       TEXT NOT NULL DEFAULT 'GENERAL',
  active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (site_id, code)
);
CREATE INDEX IF NOT EXISTS ix_zones_tenant ON zones(tenant_id);

CREATE OR REPLACE TRIGGER trg_tenants_touch BEFORE UPDATE ON tenants FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE OR REPLACE TRIGGER trg_sites_touch   BEFORE UPDATE ON sites   FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE OR REPLACE TRIGGER trg_zones_touch   BEFORE UPDATE ON zones   FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE OR REPLACE TRIGGER trg_incidents_touch BEFORE UPDATE ON incidents FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- Columnas de tenancy en tablas existentes (default 'default': los servicios actuales siguen funcionando sin cambios).
ALTER TABLE events             ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT 'default';
ALTER TABLE events             ADD COLUMN IF NOT EXISTS site_id   TEXT;
ALTER TABLE incidents          ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT 'default';
ALTER TABLE incidents          ADD COLUMN IF NOT EXISTS site_id   TEXT;
ALTER TABLE devices            ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT 'default';
ALTER TABLE devices            ADD COLUMN IF NOT EXISTS site_id   TEXT;
ALTER TABLE discovered_devices ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT 'default';
ALTER TABLE discovered_devices ADD COLUMN IF NOT EXISTS site_id   TEXT;
ALTER TABLE camera_channels    ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT 'default';
ALTER TABLE camera_channels    ADD COLUMN IF NOT EXISTS site_id   TEXT;
ALTER TABLE agent_actions      ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT 'default';

SELECT vigia_add_constraint('events',             'fk_events_tenant',             $c$FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) NOT VALID$c$);
SELECT vigia_add_constraint('incidents',          'fk_incidents_tenant',          $c$FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) NOT VALID$c$);
SELECT vigia_add_constraint('devices',            'fk_devices_tenant',            $c$FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) NOT VALID$c$);
SELECT vigia_add_constraint('discovered_devices', 'fk_discovered_devices_tenant', $c$FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) NOT VALID$c$);
SELECT vigia_add_constraint('camera_channels',    'fk_camera_channels_tenant',    $c$FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) NOT VALID$c$);
SELECT vigia_add_constraint('agent_actions',      'fk_agent_actions_tenant',      $c$FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) NOT VALID$c$);

CREATE INDEX IF NOT EXISTS ix_events_tenant_ts    ON events(tenant_id, ts DESC);
CREATE INDEX IF NOT EXISTS ix_incidents_tenant    ON incidents(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_devices_tenant      ON devices(tenant_id);
