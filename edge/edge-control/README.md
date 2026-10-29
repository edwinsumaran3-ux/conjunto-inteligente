# Edge Control Plane — Block 09

Local safety boundary for gateways/ESP32-class devices. It is intentionally independent from the ERP API so a network outage does not grant unsafe authority.

## Guarantees
- durable local command spool using SQLite;
- HMAC-SHA256 command envelope verification;
- nonce + monotonic sequence replay protection;
- expiry checks;
- local safety state: armed/safe/kill_switch/quarantined;
- allowlisted command capabilities;
- deterministic fail-safe behavior when the backend is unavailable;
- reconciliation after reconnect without executing expired commands.

The signing key must come from a device/gateway secret store in production. This reference implementation does not embed secrets.
