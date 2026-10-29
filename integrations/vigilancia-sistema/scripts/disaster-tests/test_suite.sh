#!/usr/bin/env bash
set -euo pipefail
echo "=== TEST 1: Caída de worker ==="; python scripts/chaos-monkey.py --scenario kill-worker; sleep 30; curl -s http://localhost:8000/healthz
echo "=== TEST 2: Partición de Edge ==="; python scripts/chaos-monkey.py --scenario network-partition --duration 60
echo "=== TEST 3: DB caída ==="; python scripts/chaos-monkey.py --scenario kill-db --duration 45
echo "=== TEST 4: RabbitMQ caído ==="; python scripts/chaos-monkey.py --scenario kill-rabbit --duration 45
echo "=== TEST 5: Idempotencia ==="; for i in {1..5}; do curl -s -X POST http://localhost:8000/ingest -H 'Content-Type: application/json' -d '{"event_id":"11111111-1111-1111-1111-111111111111","device_id":"ESP32-T1","sequence_number":1,"timestamp":1700000000000,"type":"MOTION","priority":"SECURITY","zone":"A","payload":{}}'; done
echo "=== TEST 6: Backpressure ==="
echo "=== TEST 7: OTA rollback ==="
echo "=== TEST 8: Detección de sabotaje ==="
