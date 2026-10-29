CREATE UNIQUE INDEX IF NOT EXISTS uq_users_tenant_id ON users(tenant_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_managed_units_tenant_id ON managed_units(tenant_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_managed_properties_tenant_id ON managed_properties(tenant_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_twin_nodes_tenant_id ON twin_nodes(tenant_id, id);

CREATE TABLE IF NOT EXISTS maintenance_residents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  user_id uuid NOT NULL,
  full_name varchar(240) NOT NULL,
  phone varchar(40),
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, user_id),
  FOREIGN KEY (tenant_id, user_id) REFERENCES users(tenant_id, id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_maintenance_residents_tenant_name
  ON maintenance_residents(tenant_id, full_name);

CREATE TABLE IF NOT EXISTS maintenance_resident_units (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  resident_id uuid NOT NULL,
  unit_id uuid NOT NULL,
  valid_from date NOT NULL DEFAULT CURRENT_DATE,
  valid_until date,
  is_primary boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_until IS NULL OR valid_until >= valid_from),
  UNIQUE (tenant_id, resident_id, unit_id, valid_from),
  FOREIGN KEY (tenant_id, resident_id)
    REFERENCES maintenance_residents(tenant_id, id) ON DELETE CASCADE,
  FOREIGN KEY (tenant_id, unit_id)
    REFERENCES managed_units(tenant_id, id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_maintenance_resident_units_unit
  ON maintenance_resident_units(tenant_id, unit_id, valid_from, valid_until);
CREATE UNIQUE INDEX IF NOT EXISTS uq_maintenance_resident_primary_unit
  ON maintenance_resident_units(tenant_id, resident_id)
  WHERE is_primary AND valid_until IS NULL;

CREATE TABLE IF NOT EXISTS maintenance_vendors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  name varchar(240) NOT NULL,
  nit varchar(32) NOT NULL,
  categories text[] NOT NULL DEFAULT '{}',
  status varchar(24) NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'suspended', 'inactive')),
  documents_valid_until date,
  rating numeric(3,2) CHECK (rating IS NULL OR rating BETWEEN 0 AND 5),
  created_by uuid NOT NULL,
  updated_by uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version integer NOT NULL DEFAULT 1 CHECK (version > 0),
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, nit),
  FOREIGN KEY (tenant_id, created_by) REFERENCES users(tenant_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, updated_by) REFERENCES users(tenant_id, id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_maintenance_vendors_tenant_status
  ON maintenance_vendors(tenant_id, status, name);

CREATE TABLE IF NOT EXISTS maintenance_order_counters (
  tenant_id uuid PRIMARY KEY,
  last_number bigint NOT NULL DEFAULT 0 CHECK (last_number >= 0)
);

CREATE TABLE IF NOT EXISTS maintenance_orders (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  code varchar(32) NOT NULL,
  title varchar(240) NOT NULL,
  description text NOT NULL DEFAULT '',
  category varchar(48) NOT NULL,
  severity varchar(16) NOT NULL
    CHECK (severity IN ('info', 'low', 'medium', 'high', 'critical')),
  status varchar(24) NOT NULL
    CHECK (status IN ('pending_approval', 'critical', 'scheduled', 'in_progress',
                      'pending_quote', 'blocked', 'completed', 'cancelled')),
  property_id uuid,
  unit_id uuid,
  asset_node_id uuid,
  area_name varchar(180) NOT NULL DEFAULT '',
  zone_name varchar(180) NOT NULL DEFAULT '',
  resident_id uuid,
  vendor_id uuid,
  cost_cop numeric(14,2) CHECK (cost_cop IS NULL OR cost_cop >= 0),
  sla_due_at timestamptz,
  reporter_kind varchar(24) NOT NULL,
  reporter_name varchar(240) NOT NULL,
  requested_by uuid NOT NULL,
  approved_by uuid,
  approved_at timestamptz,
  approval_note varchar(500),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version integer NOT NULL DEFAULT 1 CHECK (version > 0),
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, code),
  FOREIGN KEY (tenant_id, property_id)
    REFERENCES managed_properties(tenant_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, unit_id)
    REFERENCES managed_units(tenant_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, asset_node_id)
    REFERENCES twin_nodes(tenant_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, resident_id)
    REFERENCES maintenance_residents(tenant_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, vendor_id)
    REFERENCES maintenance_vendors(tenant_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, requested_by)
    REFERENCES users(tenant_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, approved_by)
    REFERENCES users(tenant_id, id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_maintenance_orders_tenant_created
  ON maintenance_orders(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_maintenance_orders_tenant_status
  ON maintenance_orders(tenant_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_maintenance_orders_tenant_category
  ON maintenance_orders(tenant_id, category, created_at DESC);

CREATE TABLE IF NOT EXISTS maintenance_order_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  order_id uuid NOT NULL,
  actor_id uuid NOT NULL,
  event_type varchar(48) NOT NULL,
  from_status varchar(24),
  to_status varchar(24),
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, order_id)
    REFERENCES maintenance_orders(tenant_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, actor_id)
    REFERENCES users(tenant_id, id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_maintenance_order_events_order
  ON maintenance_order_events(tenant_id, order_id, created_at);

DO $$
DECLARE tbl text;
BEGIN
  FOREACH tbl IN ARRAY ARRAY[
    'maintenance_residents',
    'maintenance_resident_units',
    'maintenance_vendors',
    'maintenance_order_counters',
    'maintenance_orders',
    'maintenance_order_events'
  ] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tbl);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', tbl);
    EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', tbl);
    EXECUTE format(
      'CREATE POLICY tenant_isolation ON %I USING (tenant_id = NULLIF(current_setting(''app.current_tenant_id'', true), '''')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting(''app.current_tenant_id'', true), '''')::uuid)',
      tbl
    );
  END LOOP;
END $$;

CREATE OR REPLACE FUNCTION reject_maintenance_event_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'maintenance_order_events is append-only';
END;
$$;
DROP TRIGGER IF EXISTS maintenance_order_events_no_mutation ON maintenance_order_events;
CREATE TRIGGER maintenance_order_events_no_mutation
  BEFORE UPDATE OR DELETE ON maintenance_order_events
  FOR EACH ROW EXECUTE FUNCTION reject_maintenance_event_mutation();
