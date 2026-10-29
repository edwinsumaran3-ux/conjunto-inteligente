CREATE INDEX IF NOT EXISTS ix_edge_replays_tenant_device_sequence
  ON edge_transport_replays(tenant_id, device_id, sequence DESC);

CREATE INDEX IF NOT EXISTS ix_edge_replays_tenant_device_nonce
  ON edge_transport_replays(tenant_id, device_id, nonce);
