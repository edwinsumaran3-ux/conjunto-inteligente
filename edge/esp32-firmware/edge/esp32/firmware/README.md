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
# Copia el template local (no uses sus valores de ejemplo en producción)
Copy-Item include/secrets.example.h include/secrets.h
# Edita include/secrets.h con configuración del entorno

# Compilar
.\.venv\Scripts\platformio.exe run -e esp32dev

# Firmware firmado (release)
$env:SECURE_BOOT_SIGNING_KEY = 'C:\ruta\segura\secure_boot_signing.pem'
.\.venv\Scripts\platformio.exe run -e esp32dev-release
```

El perfil `esp32dev-release` exige una clave de firma externa y URI `mqtts://`, credenciales y una identidad de dispositivo configurada en `secrets.h`. Configura MQTT TLS con verificación del CA bundle. Nunca publiques la clave, credenciales ni `secrets.h`.

El perfil de release **no está certificado ni validado en hardware**. No lo flashees hasta confirmar el modelo/revisión del ESP32, flash real, particiones, clave y procedimiento de fábrica. El build local revisado se detiene por Secure Boot V1 seleccionado en vez de V2; ver [brechas y arquitectura de hardware](../../../../../docs/HARDWARE_REFERENCE_ARCHITECTURE.md).

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
- Requiere validar en la variante de silicio y el flujo de producción objetivo.

**Advertencia:** activar secure boot y flash encryption es irreversible en el chip.
Antes de aplicarlo en hardware real, verificar custodia de claves y tener un chip de respaldo.

El flujo de descarga OTA actual todavía no valida un manifiesto de versión/hash/firma ni aplica una política completa de anti-downgrade. La verificación TLS y la firma de imagen son controles distintos. Hasta cerrar y probar el flujo con el proveedor de firma y la placa objetivo, OTA de producción sigue bloqueada. NVS encryption y una cola persistente local del nodo tampoco están habilitadas.

`partitions.csv` llega a offset `0x600000` (6 MiB); no cabe en una configuración de 4 MiB. No cambies tamaños sin medir la flash real y calcular tamaño de imagen, OTA y almacenamiento.

## Pines por defecto

| Pin | Función |
|---|---|
| GPIO27 | PIR |
| GPIO26 | Magnético |
| GPIO25 | Tamper |

Modificables en `src/main.cpp` (`PIN_PIR`, `PIN_MAGNETIC`, `PIN_TAMPER`).
