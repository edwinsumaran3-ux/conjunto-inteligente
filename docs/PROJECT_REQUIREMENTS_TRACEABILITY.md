# Trazabilidad de requisitos, ZIP y brechas del proyecto

**Corte de revisión:** 2026-10-29.
**Alcance:** dos textos compartidos en la conversación, el ZIP `conjunto_inteligente_iot_industrial.zip` y el monorepo actual. Revisión estática de archivos y validaciones puntuales; no implica que todos los servicios se hayan desplegado.

## Resumen ejecutivo

El ZIP no es un sistema punta a punta listo para añadir sin cambios: es una propuesta pequeña de integración. Varias capacidades ya están implementadas en módulos existentes con arquitectura y contratos diferentes. Otras son incompletas en ambos lados. Se preserva el monorepo y se integra el objetivo mediante políticas, matriz de requisitos y endurecimiento del transporte del firmware; no se copian componentes duplicados ni se presentan pruebas mock como pruebas de dispositivo.

| Área | Estado real en el proyecto | Acción / brecha |
|---|---|---|
| ERP, mantenimiento y aprobaciones | API FastAPI con módulos, frontend ERP y flujos de mantenimiento; ver [README raíz](../README.md) | Mantener como fuentes existentes; no recrear el ERP en un servicio paralelo del ZIP. |
| Gemelo BIM / IFC | Módulo `digital_twin` con ingestión/inspección IFC, geometría, diagnósticos, APIs y pruebas | La correlación concreta telemetría→activo CMMS→revisión IFC debe probarse con IDs reales; el binder del ZIP no se integra automáticamente. |
| Telemetría | Normalización de unidades y clasificación de calidad (incluye stale/bad/fuera de rango), ingestión batch y outbox | Falta HIL por tipo de sensor, puntos/umbrales aprobados y reconciliación extremo a extremo sobre hardware real. |
| Autenticación y anti-replay | `edge_transport` firma Ed25519 de gateway, credenciales acotadas por tenant, nonce/secuencia durable en PostgreSQL y límites de ingestión | El ESP32 ahora verifica el broker cuando usa `mqtts://`, pero todavía no firma cada evento ni tiene identidad criptográfica individual; TLS de transporte no es autenticación del mensaje. El autenticador Ed25519/Redis del ZIP duplicaría el límite de gateway y no resuelve el contrato MQTT actual. |
| Seguridad de OTA | Release configura secure boot/flash encryption y el gestor actual delega aceptación de imagen a ESP-IDF | El gestor aún no descarga/valida un manifiesto con versión/hash/firma ni usa una política completa de anti-downgrade. El ejemplo del ZIP no demuestra autoría: el hash esperado y la comparación de versiones no bastan. |
| Provisionamiento | Configuración compilada desde `secrets.h` local ignorado por Git | No hay flujo de provisionamiento de técnico con identidad/desafío/rotación. El `ProvisioningManager` del ZIP solo consulta estado; no implementa provisioning seguro. |
| Edge y caídas de conectividad | Gateway C++ con SQLite/WAL y reintentos; API central separada | La cola cubre gateway→API, no una caída sostenida nodo→broker. No hay evidencia de failover físico de dos gateways ni RPO/RTO probado. |
| Infraestructura | Compose separados por componente/perfil; no hay una compose única raíz según README/Makefile | El Compose del ZIP es local y no se mezcla como despliegue productivo; no define app API/alta disponibilidad ni política de producción. |
| Frontend | `00_ERP_Enterprise_v5/frontend` es la aplicación ERP; `frontend/centro-mando` es una referencia visual estática descrita como preparada para reemplazar datos demo | No afirmar que el centro de mando está conectado, que el modelo 3D es operativo o que una imagen conceptual es captura real. Hace falta validación visual y conexión real de cada panel. |
| Gobernanza del agente | Los requisitos estaban solo en el texto compartido | Se añaden [instrucciones Copilot](../.github/copilot-instructions.md) y [política operativa](./AGENT_OPERATING_POLICY.md). La conexión a API/casos y el cumplimiento runtime siguen por implementar. |
| Hardware industrial | ESP32 con sensores discretos y gateway edge presentes | No hay BOM, esquema eléctrico/PCB, PLC validado, diseño de protección/aislamiento, inventario del sitio ni prueba física industrial. Ver [arquitectura de hardware](./HARDWARE_REFERENCE_ARCHITECTURE.md). |

## Revisión de los archivos del ZIP

| Archivo o grupo | Hallazgo frente al repositorio | Decisión |
|---|---|---|
| `backend/.../device_authenticator.py` | Verifica firma Ed25519, pero usa `SET NX EX` con TTL como antireplay; la secuencia puede repetirse al expirar. No hay límite/tipo de esquema y no comparte canonicalización/firmware con el código ESP32 existente. | No copiar; usar el transporte existente y cerrar el contrato nodo→broker antes de añadir otro autenticador. |
| `backend/.../bim_asset_binder.py` | Ofrece una abstracción de binding y cálculo de desviación, pero depende de `networkx` y usa `nx.descendants` solo como alcance topológico; límites/unidades de IFC requieren modelo aprobado. | No duplicar `digital_twin`; el binding y reglas de salud deben residir en la capa de dominio existente y usar catálogos reales. |
| `firmware/common/ota_manager.h` | Calcula SHA-256 de los bytes y exige TLS CA, pero el hash no autentica el editor; `isNewerVersion` acepta cualquier versión distinta, incluso una anterior. El código indica que semver debe sustituirse. | No copiar. Endurecer OTA en el firmware ESP-IDF existente después de definir manifiesto, clave pública y hardware/particiones. |
| `firmware/common/provisioning_manager.h` | Declara explícitamente que solo consulta NVS y que no implementa BLE/provisionamiento seguro. | No presentarlo como función; el proceso de fábrica/operación es un bloqueo abierto. |
| `secure_config.h` | Define nombres de claves; los nombres de namespace NVS no cifran los valores. | La política se mantiene: cifrado NVS requiere configuración y procedimiento de fábrica. |
| `test_device_authenticator.py` | Casos unitarios con `Mock`; prueba el resultado simulado de Redis, no atomicidad/concurrencia ni persistencia real. | Se considera cobertura unitaria, no prueba de integración ni HIL. |
| `infra/docker-compose.yml`, Mosquitto | Compose local; `mosquitto.conf` permite conexión anónima en `0.0.0.0:1883` y declara expresamente perfil de desarrollo. | No importar en despliegue de producción ni afirmar HA por tener volúmenes o `restart`. |
| `firmware/platformio.ini`, `test_telemetry_contract.cpp` | Proyecto Arduino paralelo a la implementación actual ESP-IDF; la prueba solo verifica que un `float` sea finito y que un `uint32_t` sea >= 0 (condición tautológica). No valida publicación, firma, secuencia persistente ni sensores. | No crear una segunda base de firmware. Portar contratos necesarios a la fuente vigente con pruebas compatibles. |
| Documentación de hardware/seguridad | Contiene límites correctos sobre SHA-256, BLE, NVS, BIM/MEP, tenant y pruebas físicas. | Conservar sus requisitos en esta matriz y la arquitectura de referencia, sin copiar sus afirmaciones de pruebas no reproducibles. |

## Hallazgos críticos verificados

1. **Configuración MQTT de producción:** el cliente MQTT ESP-IDF no adjuntaba verificación de certificado. Se endureció el cliente para adjuntar el CA bundle al usar `mqtts://` y rechazar `mqtt://` en release. Release también se detiene si aún usa credenciales de ejemplo. Esto no configura mTLS ni establece identidad única por nodo.
2. **Ciclo de arranque:** el firmware reiniciaba si Wi-Fi no aparecía en 30 segundos. Ahora permanece sin conexión y continúa su flujo local; como no hay outbox persistente en ESP32, los eventos que no logra publicar aún pueden perderse.
3. **NVS:** el arranque borraba automáticamente toda la partición NVS ante `NO_FREE_PAGES`/`NEW_VERSION_FOUND`. Ahora queda detenido sin destruir configuración; la recuperación requiere procedimiento explícito.
4. **Particiones/Windows:** la configuración anterior mezclaba un mapa de 6 MiB, el valor de 2 MiB de `sdkconfig` y los 4 MiB predeterminados de la placa PlatformIO. Además, `^6.7.0` resolvió a `espressif32@6.13.0`, y un `sdkconfig` release local ignorado persistía Secure Boot V1. Se fijó la plataforma en `6.13.0`, se creó el board local de 2 MiB, se aisló el `sdkconfig` release en `.pio/` y se separaron particiones de desarrollo y release; ambas tablas validan contra 2 MiB. El build dev pasa y su imagen debug ocupa 1,282,457 bytes, por lo que no cabe en una ranura OTA release de 851,968 bytes. El build release se detiene antes de compilar porque el `sdkconfig` fresco selecciona `ESP32_REV_MIN=0` y Secure Boot V1; falta la revisión real, necesaria para seleccionar V2 RSA. La flash de 2 MiB fue informada, aún no leída físicamente. No se generó ni usó una clave ni se flasheó hardware.
5. **Flujo OTA:** `src/ota_manager.cpp` aún no procesa el manifiesto JSON descrito por `ota_manager.hpp`; el propio código pospone la validación de versión/hash/manifiesto. La firma de imagen debe validarse con la clave y perfil de Secure Boot reales antes de aceptar OTA.
6. **Pérdida de datos en nodo:** el gateway almacena/reintenta después de recibir mensajes, pero el nodo no tiene cola durable confirmada. La arquitectura debe resolver tamaño de cola, partición, ACK, secuencia durable, retención y recuperación antes de declarar store-and-forward de extremo a extremo.

## Reglas para los siguientes cortes

1. Recibir información del sitio y placa objetivo; ejecutar lectura no destructiva de chip/flash antes de ajustar configuraciones.
2. Congelar contrato firmado nodo→broker→gateway→API: canonicalización, esquema/versionado, identidad/tenant confiable, secuencia durable, calidad/units, ACK e idempotencia.
3. Diseñar y probar el outbox de nodo acorde con memoria/flash disponibles y límites de desgaste. No usar RAM como sustituto de persistencia ni confirmar el envío antes del ACK requerido.
4. Definir proveedor de firma OTA/HSM, manifiesto firmado, clave pública de verificación, anti-rollback y flujo de rollback/recuperación. Mantener claves privadas fuera del repo y chat.
5. Acordar binding sensor-dispositivo-activo-CMMS-GlobalId/revisión IFC con pruebas por tenant y modelo IFC real; umbrales solo desde ingeniería/puesta en servicio aprobada.
6. Definir red OT, certificados por dispositivo, ACLs MQTT, firewall, VLAN, redundancia de energía/red, RPO/RTO y plan de respuesta a incidentes.
7. Crear BOM, esquemas/PCB, seguridad eléctrica, selección de sensores y aceptación en sitio solo después del levantamiento y revisión de ingeniería competente.
8. Completar pruebas unitarias, integración con servicios reales descartables, HIL, pruebas de fallo y commissioning. Reportar cada nivel por separado; simulación no sustituye a hardware.

## Datos que faltan para cerrar el diseño físico

- Número de edificios, zonas, equipos, puntos y criticidad; planos BIM/MEP vigentes y CMMS.
- Variable, rango, unidad, precisión, frecuencia y límites aprobados de cada punto.
- Voltajes, tableros, cargas, puesta a tierra, fuentes/UPS, trayectos y distancias de cable.
- Ambiente físico, IP/NEMA, temperatura/humedad, EMI, mantenimiento y certificaciones.
- Redes, cobertura, segmentación, switches, energía redundante y conexión de respaldo.
- Referencia/revisión exacta del chip, capacidad de flash, interfaces y aprobación de fabricación.
- Volumen/retención de telemetría, RPO/RTO, perfiles de notificación de emergencia y matriz de autorizaciones.
