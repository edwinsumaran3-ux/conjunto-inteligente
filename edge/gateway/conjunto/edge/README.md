# Edge Gateway — Conjunto Inteligente

Gateway nativo en C++ 20 que conecta el mundo IoT (ESP32, cámaras, sensores) con el core de la plataforma.

## Responsabilidades

1. **Suscribirse** a los eventos MQTT del broker (`conjunto/+/events`).
2. **Encolar** los eventos en SQLite local con WAL (sobrevive reinicios y caídas de red).
3. **Reenviar** con backoff exponencial al core o al AI Orchestrator vía HTTP o HTTPS validado.
4. **Exponer** salud y métricas en `:8080`.

## Por qué C++

- Latencia sub-100 ms en recepción de eventos.
- Footprint mínimo (corre en ARM de bajo costo).
- Control determinista de memoria y timeouts.
- Sin GC → sin pausas impredecibles.

## Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `EDGE__MQTT_HOST` | `localhost` | Host del broker |
| `EDGE__MQTT_PORT` | `1883` | Puerto del broker |
| `EDGE__MQTT_TOPIC` | `conjunto/+/events` | Topic de suscripción |
| `EDGE__MQTT_CLIENT_ID` | autogenerado | ID único del cliente |
| `EDGE__MQTT_USERNAME` | — | Usuario MQTT |
| `EDGE__MQTT_PASSWORD` | — | Password MQTT |
| `EDGE__MQTT_USE_TLS` | `false` | Activar TLS |
| `EDGE__MQTT_CA_FILE` | — | CA para TLS |
| `EDGE__MQTT_QOS` | `1` | QoS 0, 1 o 2 |
| `EDGE__FORWARD_URL` | `http://localhost:8000/analyze/reception` | Endpoint destino (`http://` o `https://`) |
| `EDGE__API_KEY` | — | Bearer token |
| `EDGE__HTTP_TIMEOUT_MS` | `5000` | Timeout HTTP |
| `EDGE__BUFFER_PATH` | `edge-events.db` | Ruta SQLite |
| `EDGE__BATCH_SIZE` | `50` | Eventos por lote |
| `EDGE__FLUSH_INTERVAL_MS` | `1000` | Pausa entre ciclos |
| `EDGE__INITIAL_BACKOFF_MS` | `500` | Backoff inicial |
| `EDGE__MAX_BACKOFF_MS` | `30000` | Backoff máximo |
| `EDGE__BACKOFF_MULTIPLIER` | `2.0` | Factor de crecimiento |
| `EDGE__MAX_RETRIES` | `20` | Reintentos máximos por evento |
| `EDGE__HEALTH_PORT` | `8080` | Puerto del servidor de salud |
| `EDGE__LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARN`, `ERROR` |

## Build

```bash
# Dependencias
sudo apt install libpaho-mqtt-dev libsqlite3-dev cmake ninja-build build-essential

# Configurar
cmake --preset=dev

# Compilar
cmake --build --preset=dev -j

# Probar
ctest --preset=dev --output-on-failure

# Ejecutar
./build/dev/gateway/conjunto-edge-gateway
```

## Endpoints de salud

- `GET /health` → liveness.
- `GET /ready` → readiness + buffer size.
- `GET /metrics` → contadores operativos.

## Límites conocidos

- TLS con certificados reales requiere `EDGE__MQTT_USE_TLS=true` y `EDGE__MQTT_CA_FILE`.
- La autenticación mTLS por dispositivo se implementa en producción (Bloque 4, firmware ESP32).
- El buffer SQLite no tiene compactación periódica: se rota cuando se supera el tamaño configurado (pendiente, ADR futuro).

## Transporte autenticado con el Core — Bloque 12

El gateway puede publicar directamente al ERP mediante `POST /api/v1/edge-transport/events` usando identidad Ed25519 por dispositivo, nonce y secuencia persistente. El mismo gateway puede consultar comandos firmados y publicarlos por MQTT al dispositivo.

Variables nuevas obligatorias en producción:

| Variable | Descripción |
|---|---|
| `EDGE__DEVICE_ID` | UUID del gateway registrado en `edge_devices` |
| `EDGE__DEVICE_PRIVATE_KEY` | Ruta a la clave privada Ed25519 fuera del repositorio |
| `EDGE__TENANT_ID` | UUID del tenant propietario |
| `EDGE__COMMAND_VERIFY_KEY` | Clave HMAC usada para verificar comandos del core (debe coincidir con `EDGE_COMMAND_HMAC_KEY` del backend) |
| `EDGE__FORWARD_URL` | URL del endpoint `/api/v1/edge-transport/events` |

La configuración de producción **no permite iniciar** el gateway sin identidad, tenant y clave de verificación de comandos.
Las publicaciones y consultas de comandos admiten HTTPS con validación del certificado del servidor; la confianza se toma del almacén de CA del sistema. En producción, configura `EDGE__FORWARD_URL` con `https://`.
