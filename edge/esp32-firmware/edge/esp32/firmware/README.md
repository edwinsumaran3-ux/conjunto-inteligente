# Firmware ESP32 — Conjunto Inteligente

Firmware del nodo sensor (PIR, magnético, tamper) que publica eventos MQTT
compatibles con el contrato `Event` del Edge Gateway.

## Por qué ESP-IDF y no Arduino

- Secure boot, flash encryption, OTA firmada: features de producción del framework oficial.
- Control de tareas y memoria de bajo nivel.
- Espressif mantiene ESP-IDF como referencia, con soporte a largo plazo.

## Requisitos

- PlatformIO Core (`.venv/Scripts/python.exe -m pip install -r requirements-dev.txt` en Windows)
- ESP-IDF 5.1 (PlatformIO lo instala automáticamente)
- Hardware: ESP32-WROOM-32 o compatible
- Broker MQTT accesible (Mosquitto local del Bloque 3 o broker público de pruebas)

Para crear un entorno Python aislado en Windows:

```powershell
py -3.11 -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -r requirements-dev.txt
```

## Estructura

- `src/config.*` — configuración inmutable cargada desde `secrets.h`.
- `src/wifi_manager.*` — WiFi con reconexión automática.
- `src/mqtt_manager.*` — MQTT sobre TLS con last-will y reconexión.
- `src/event_publisher.*` — construye el JSON del contrato Event y lo publica.
- `src/heartbeat.*` — publica heartbeat periódico.
- `src/ota_manager.*` — OTA HTTPS con verificación de firma.
- `src/sensors/` — abstracciones de sensores con debounce.
- `src/backoff.*` — backoff exponencial reutilizable (testeable en nativo).

## Compilar

```bash
# Copia el template de secretos
cp include/secrets.example.h include/secrets.h
# Edita secrets.h con tus valores reales

# Compilar
pio run -e esp32dev

# Firmware firmado (release)
export SECURE_BOOT_SIGNING_KEY=/ruta/a/secure_boot_signing.pem
pio run -e esp32dev-release
```

El perfil `esp32dev-release` falla si no existe la clave de firma o no se genera el binario firmado; nunca publica silenciosamente un artefacto sin firma. La clave debe provisionarse desde un gestor de secretos y no guardarse en el repositorio.

## Flashear

```bash
# Vía USB
pio run -e esp32dev -t upload

# Monitor serial
pio device monitor -e esp32dev -b 115200
```

## Probar sin hardware

```bash
# Tests unitarios nativos (C++ puro)
pio test -e native
```

## Probar con Wokwi

1. Abrir https://wokwi.com/projects/new/esp32
2. Copiar `diagram.json` y `wokwi.toml`.
3. `pio run -e wokwi`.
4. Subir `.pio/build/wokwi/firmware.bin`.

## Variables de compilación

- `-DFW_ENV=dev` → logs verbose, sin secure boot.
- `-DFW_ENV=release` → logs mínimos, activa firma.
- `-DWOKWI_SIM=1` → desactiva hardware real en simulación.

## Configuración (vía `secrets.h`)

| Constante | Descripción |
|---|---|
| `WIFI_SSID` / `WIFI_PASS` | Credenciales WiFi |
| `MQTT_URI` | URI del broker (`mqtts://host:8883` para TLS) |
| `MQTT_USERNAME` / `MQTT_PASSWORD` | Credenciales MQTT |
| `MQTT_CLIENT_ID` | ID único del cliente |
| `TENANT_ID` | Tenant al que pertenece el nodo |
| `DEVICE_ID` | Identificador físico del nodo |
| `DEVICE_TYPE` | Ej: `sensor.pir`, `sensor.magnetic` |
| `OTA_MANIFEST_URL` | Endpoint HTTPS del manifest OTA |

## Contrato de eventos publicados

Los eventos van al topic `conjunto/<TENANT_ID>/events` con este JSON:

```json
{
  "id": "esp32-014-0A1B2C3D-0001",
  "tenant_id": "conjunto-abc-001",
  "device_id": "esp32-pir-014",
  "type": "sensor.pir",
  "payload": {"zone": "P1-Z3", "duration_s": 1},
  "timestamp_ms": 1730512345678
}
```

Debe coincidir con el contrato `Event` que espera el Edge Gateway (Bloque 3).
`test/test_event_payload.cpp` verifica la generación de ID sin hardware.

## Seguridad (producción)

`sdkconfig.defaults.release` incluye:

- Secure boot V2 firmado con RSA.
- Flash encryption en modo release.
- Deshabilitación del ROM console.
- OTA rechaza binarios sin firma válida.

**Advertencia:** activar secure boot y flash encryption es irreversible en el chip.
Antes de aplicarlo en hardware real, verificar custodia de claves y tener un chip de respaldo.

## Pines por defecto

| Pin | Función |
|---|---|
| GPIO27 | PIR |
| GPIO26 | Magnético |
| GPIO25 | Tamper |

Modificables en `src/main.cpp` (`PIN_PIR`, `PIN_MAGNETIC`, `PIN_TAMPER`).
