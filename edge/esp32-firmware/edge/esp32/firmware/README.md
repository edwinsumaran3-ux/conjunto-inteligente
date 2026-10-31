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

## Perfil para sensores del conjunto

El entorno `esp32dev-sensors` agrega el montaje de la guía de cableado sin reemplazar
el perfil original `esp32dev`. Usa un ESP32 clásico compatible con ESP-IDF, como
ESP32-WROOM-32 DevKit. No uses este binario en ESP32-C3, S2, S3 o C6 sin adaptar y
verificar el mapeo de pines.

| Sensor | Pin en la guía | Interfaz configurada | Evento MQTT |
|---|---|---|---|
| DHT22 | GPIO4 | DHT de una señal, lectura cada 5 s | `sensor.environment` |
| DS18B20 | GPIO15 | Bus 1-Wire con RMT; pull-up externo requerido | `sensor.water_temperature` |
| Flotador de nivel | GPIO27 | Entrada digital activa en bajo, publica al iniciar y al cambiar | `sensor.water_level` |
| ACS712 | GPIO35 | ADC1 canal 7; publica el promedio de 16 lecturas ADC crudas | `sensor.current_raw` |
| Presión analógica | GPIO34 | ADC1 canal 6; publica el promedio de 16 lecturas ADC crudas | `sensor.pressure_raw` |
| PZEM-004T v3.0 | GPIO16 TX / GPIO17 RX | UART2, 9600 baudios, 8-N-1 | `sensor.energy` |

Las mediciones periódicas se toman cada cinco segundos y se publican en el topic
`conjunto/<TENANT_ID>/events`, con el sobre de eventos que ya utiliza el gateway.
El PZEM responde a la consulta de registros Modbus RTU; si no está conectado, los
demás sensores siguen funcionando.

### Conexión de baja tensión y límites eléctricos

- Alimenta el ESP32 por USB y conecta GND común entre la placa y los módulos de
  sensores de baja tensión.
- DHT22: VCC a 3V3, GND a GND y DATA a GPIO4. Añade una resistencia de 4.7 kOhm
  entre DATA y 3V3 si el módulo no la incorpora.
- DS18B20: DATA a GPIO15; coloca una resistencia externa de 4.7 kOhm entre DATA
  y 3V3. GPIO15 es un pin de configuración de arranque del ESP32 clásico: si la
  placa no arranca de forma estable con el sensor conectado, mueve DATA a un GPIO
  libre y cambia el pin en `src/sensors/installation_sensors.cpp`.
- Flotador: señal a GPIO27, con el contacto de alarma llevando la entrada a GND.
  El perfil interpreta nivel bajo como “agua detectada”; invierte esa lógica en
  `InstallationSensors::poll` si el módulo instalado opera al contrario.
- ACS712 y presión: GPIO35/GPIO34 son entradas ADC solamente. **Nunca conectes
  directamente a una entrada ESP32 una salida que pueda superar 3.3 V.** El
  ACS712 suele alimentarse a 5 V; instala y dimensiona un acondicionador/divisor
  de nivel apropiado y seguro, comprueba la salida máxima del sensor con
  instrumentos antes de conectar y recalibra para el modelo exacto. El software
  informa cuentas ADC sin convertirlas a amperios ni a unidades de presión.
- PZEM, lado de comunicación: TX del PZEM hacia RX GPIO17; RX del PZEM hacia TX
  GPIO16. Verifica niveles lógicos y el manual de la versión exacta del módulo.
- **El PZEM-004T se utiliza para medir red eléctrica. Su lado de tensión/corriente
  puede implicar voltajes letales. No conectes cables de red en una protoboard ni
  manipules una instalación energizada.** La instalación de red, aislamiento,
  pinza y módulo debe hacerla personal calificado. Trabaja únicamente con el
  circuito desenergizado y la instalación verificada.

### Compilar y probar este perfil

Desde esta carpeta del firmware:

```powershell
.\.venv\Scripts\platformio.exe run -e esp32dev-sensors
.\.venv\Scripts\platformio.exe test -e native
```

La primera compilación descarga los componentes declarados en
`src/idf_component.yml`. Configura SSID, contraseña, broker MQTT TLS, usuario,
contraseña, tenant e ID del equipo en una copia local de `include/secrets.example.h`
llamada `include/secrets.h`; ese archivo está ignorado por Git y no debe compartirse.
Sin credenciales el firmware compila, pero Wi-Fi y las publicaciones permanecen
desconectados.

La plantilla de PlatformIO de este proyecto reserva 2 MB de flash. Confirma la
capacidad real de la placa y el módulo antes de cargar el firmware. El perfil de
desarrollo no habilita secure boot, pero **no se ha cargado ni probado este perfil
en la placa física**; compilar no verifica el cableado ni la seguridad de las
lecturas. No ejecutes el objetivo `upload` hasta identificar el chip, confirmar la
flash y revisar todas las conexiones. Nunca habilites las opciones irreversibles
de firma/flash encryption a modo de prueba.
