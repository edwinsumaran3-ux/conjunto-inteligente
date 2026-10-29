# Physical Edge Transport — producción real

Este bloque conecta el gateway físico con el core mediante un contrato de transporte autenticado. No depende de un usuario humano ni de datos simulados.

## Flujo real

1. ESP32/cámara/sensor publica un evento MQTT al gateway.
2. El gateway lo persiste en SQLite WAL.
3. El gateway asigna una secuencia persistente.
4. Firma el envelope con la **clave privada Ed25519 del gateway**.
5. Envía `POST /api/v1/edge-transport/events`.
6. El backend verifica la firma contra la clave pública registrada para ese `edge_device`.
7. PostgreSQL RLS conserva el aislamiento por tenant.
8. El nonce + secuencia se registran en `edge_transport_replays`.
9. El evento pasa a `edge_event_spool` y continúa hacia el plano de inteligencia/operaciones.
10. Los comandos aprobados pueden volver por `/edge-transport/commands/{gateway_id}/signed`; el gateway verifica la firma HMAC del comando antes de publicarlo al dispositivo por MQTT.

## Credenciales

Generar una identidad Ed25519:

```bash
./scripts/provision_edge_identity.sh /secure/edge/device-001 <DEVICE_UUID>
```

**Nunca** subir `device-private.pem` al repositorio.

## Variables obligatorias del gateway

- `EDGE__DEVICE_ID`
- `EDGE__DEVICE_PRIVATE_KEY`
- `EDGE__TENANT_ID`
- `EDGE__COMMAND_VERIFY_KEY` (mínimo 32 bytes)
- `EDGE__FORWARD_URL=https://<core>/api/v1/edge-transport/events`

En producción también deben estar habilitados TLS/MQTT autenticado y gestión externa de secretos.

## Estado de verificación

Validado localmente:

- firma Ed25519 C++ → verificación Ed25519 Python: OK
- replay nonce/sequence: implementado
- RLS: implementado en migración
- persistencia WAL del gateway: existente y conservada
- tests Python del nuevo transporte: OK

No se declara validación física hasta conectar hardware real y ejecutar pruebas HIL/failover con el hardware instalado.
