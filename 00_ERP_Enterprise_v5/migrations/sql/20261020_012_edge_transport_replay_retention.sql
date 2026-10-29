CREATE INDEX IF NOT EXISTS ix_edge_replays_tenant_device_created
  ON edge_transport_replays(tenant_id, device_id, created_at, row_id);
