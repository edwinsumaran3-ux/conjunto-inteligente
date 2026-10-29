# 08 — Auto-descubrimiento de equipos y malla de sensores

## Auto-descubrimiento y conexión automática

`edge-gateway/src/device_autodiscovery.py` sondea un rango de direcciones (puertos
80/554/8000), identifica marca/modelo/protocolo por firma de cabecera HTTP
(`SIGNATURES`) y, para equipos `NATIVE`/`COMPATIBLE`, construye de inmediato la URL de
stream y marca `auto_connected=True` — sin pasos manuales adicionales, tal como se
pidió ("la conexión a los equipos debe ser automática").

Endpoints:
- `POST /discovery/scan {addresses:[...], zone}` — sondea y conecta.
- `GET /discovery/devices` — inventario en memoria del edge-gateway (disponible aunque
  el backend central esté offline).

Cada hallazgo también se reenvía como evento `DEVICE_DISCOVERED` al pipeline central,
donde `services/worker-pool/src/discovery_projector.py` lo proyecta a la tabla durable
`discovered_devices` (auditoría histórica, sobrevive a un reinicio del edge).

**Extensión pendiente para producción real**: `SIGNATURES` cubre firmas genéricas de
ejemplo (Hikvision, Dahua, ONVIF/RTSP genérico); añadir fabricantes reales requiere
solo agregar entradas a esa lista, sin tocar el resto del módulo.

## Malla de sensores (cascada láser/IR → cámaras)

`edge-gateway/src/sensor_mesh.py` mantiene la topología `sensor_id -> [camera_id, ...]`
(configurable por `MESH_TOPOLOGY_JSON` o `POST /mesh/link`). Cuando el firmware reporta
`LASER_TRIPWIRE` o `IR_BARRIER`, el gateway publica de inmediato (sin esperar al
backend central — autonomía de borde) un comando MQTT `cameras/{id}/focus` a cada
cámara vecina. El mismo evento se reenvía como `PERIMETER_BREACH` al pipeline central,
donde `PerimeterAgent` lo audita y también propone `FOCUS_CAMERA` (auto-aprobado, sin
gate humano, por ser una acción reversible).

`GET /mesh/topology` expone el mapa completo para el tablero de topología del
dashboard (`EquipmentTopologyBoard`).
