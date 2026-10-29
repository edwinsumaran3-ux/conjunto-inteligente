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
- Broker MQTT privado accesible por TLS; no se usa un broker público por defecto.

PlatformIO queda fijado en `espressif32@6.13.0` para evitar que Windows resuelva una
versión diferente de plataforma. El board local `esp32dev_2mb` aplica los 2 MB informados
en desarrollo, release y Wokwi, en vez de heredar los 4 MB predeterminados de `esp32dev`.
Desarrollo usa una partición de aplicación grande para pruebas por USB; release conserva
dos ranuras OTA de 832 KiB cada una y 256 KiB de almacenamiento. La compilación comprueba
si el binario cabe en el perfil elegido. Antes de flashear, lee la flash y revisión reales
de la placa; el tamaño informado aún no se ha confirmado por hardware.

Para crear un entorno Python aislado en Windows:

```powershell
py -3.11 -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -r requirements-dev.txt
$env:PYTHONUTF8 = '1'
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
# Copia el template local, agrega configuración real y guarda el archivo solo localmente
Copy-Item include/secrets.example.h include/secrets.h
# Rellena include/secrets.h; vacío significa que Wi-Fi/MQTT permanecen desconectados.

# Compilar
.\.venv\Scripts\platformio.exe run -e esp32dev

# Firmware firmado (release)
$env:SECURE_BOOT_SIGNING_KEY = 'C:\ruta\segura\secure_boot_signing.pem'
.\.venv\Scripts\platformio.exe run -e esp32dev-release
```

El perfil `esp32dev-release` usa un `sdkconfig` aislado bajo `.pio/` y exige Secure Boot V2,
una clave de firma externa, URI `mqtts://`, credenciales e identidad de dispositivo en
`secrets.h`. Configura MQTT TLS con verificación del CA bundle. Nunca publiques claves,
credenciales ni `secrets.h`.

El perfil de release **no está listo para firmar ni certificado en hardware**. Su
configuración aislada selecciona Secure Boot V1 con la revisión mínima predeterminada y
ESP-IDF detiene el build (`Secure Boot v1 is not supported`). Secure Boot V2 RSA requiere
ESP32 clásico revisión 3 o posterior; no se debe elevar la revisión mínima para ocultar el
bloqueo. Confirma el modelo/revisión del chip y el proceso autorizado de firma antes de
habilitar el release o flashear. Ver
[brechas y arquitectura de hardware](../../../../../docs/HARDWARE_REFERENCE_ARCHITECTURE.md).

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

En Windows, los tests nativos requieren GCC de MSYS2 UCRT64 en `PATH`:

```powershell
$env:PATH = "C:\msys64\ucrt64\bin;$env:PATH"
.\.venv\Scripts\platformio.exe test -e native
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

`partitions.csv` termina en `0x200000` (2 MiB) y reserva una app grande para desarrollo.
`partitions.release.csv` reserva dos apps OTA de 832 KiB cada una y 256 KiB de
almacenamiento. No flashees otra capacidad ni un módulo distinto sin verificar la flash
física y el tamaño de la imagen.

## Pines por defecto

| Pin | Función |
|---|---|
| GPIO27 | PIR |
| GPIO26 | Magnético |
| GPIO25 | Tamper |

Modificables en `src/main.cpp` (`PIN_PIR`, `PIN_MAGNETIC`, `PIN_TAMPER`).
