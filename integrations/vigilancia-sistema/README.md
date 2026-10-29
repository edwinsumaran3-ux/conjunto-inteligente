# Vigilancia Distribuida Tolerante a Fallos — versión endurecida

Esta versión corrige los fallos de integración del paquete original y convierte el flujo principal en un sistema ejecutable de extremo a extremo: ESP32 → MQTT/Edge → Ingestion → RabbitMQ → Worker → PostgreSQL → correlación/incidentes → alertas → dashboard.

## Correcciones principales
- El Edge ya no reemplaza el evento original por las acciones de reglas locales.
- ACK `BUFFERED` no destruye eventos: el Edge mantiene un journal persistente y reintenta.
- PostgreSQL es la autoridad durable para idempotencia; se añadió unicidad `(device_id, sequence_number)`.
- Los timestamps del firmware usan epoch relativo al boot de ESP32; para producción real se debe sincronizar NTP antes de emitir eventos y/o usar RTC seguro.
- Worker publica eventos procesados al exchange fanout para que Correlation Engine realmente reciba datos.
- Correlation Engine publica incidentes; Incident Core los consume y Notification Service recibe alertas.
- Dashboard consume endpoints reales `/events` y `/incidents`; se eliminaron cámaras y estados falsos.
- Se eliminaron secretos hardcodeados del compose; se usa `.env` fuera del repositorio.
- Redis usa autenticación y persistencia AOF.
- Se añadieron healthchecks, usuarios sin privilegios en contenedores y versiones fijadas.
- Firma ECDSA ahora usa DER correctamente al verificar.
- Se eliminó el `except Exception: return True` que convertía firmas inválidas en válidas.
- Buffer ESP32 usa LittleFS en lugar de guardar solo índices en NVS.

## Arranque local
1. Copia `infrastructure/.env.example` a `infrastructure/.env` y cambia todos los secretos.
2. Ejecuta `cd infrastructure && docker compose up --build`.
3. API: `http://localhost:8000/healthz`.
4. Edge: `http://localhost:8001/healthz`.
5. Dashboard: `http://localhost:5173`.
6. Prometheus: `http://localhost:9090`.

## Producción real
Este repositorio no contiene certificados, claves privadas, credenciales, modelos de IA ni una CA real. Deben provisionarse mediante un gestor de secretos/PKI y configuración de infraestructura. Antes de producción deben ejecutarse pruebas hardware, carga, pérdida de energía, partición de red, recuperación de PostgreSQL/RabbitMQ, OTA firmado y pruebas de penetración.

## Ampliación: agentes autónomos, cámaras 1-24, auto-descubrimiento y fusión de seguridad

Este repositorio incorpora además una ampliación mayor (orquestador de agentes, malla de
sensores láser/IR en cascada, auto-descubrimiento y conexión automática de equipos, grid de
cámaras 1-24 con captura/grabación/edición) y una fusión con un segundo esqueleto recibido en
paralelo (.NET, "VigilanciaPlatform"), de donde se portaron piezas de hardening de seguridad y
el patrón de comandos firmados fail-closed para equipos físicos. Ver:

- `docs/07-orquestacion-agentes.md`
- `docs/08-auto-descubrimiento-malla-sensores.md`
- `docs/09-frontend-camaras-media.md`
- `docs/10-fusion-unificacion-plataforma.md` — **por qué y cómo se fusionaron ambos proyectos**, qué se portó, qué quedó como frontera documentada y qué no se adoptó.

Servicio nuevo: `services/agent-orchestrator` (puerto 8002, ver `docker-compose.yml`).
Endpoints nuevos en `edge-gateway`: `/discovery/scan`, `/discovery/devices`, `/mesh/link`,
`/mesh/topology`. Pestañas nuevas en el dashboard: Agentes, Topología, Descubrimiento.


## Integración con Conjunto Inteligente

Esta copia forma parte del monorepo `phase4` bajo `integrations/vigilancia-sistema`. Su plano neural compartido es `services/ai-agent/conjunto-ai-block2`; se eliminó el gateway LLM duplicado para evitar dos cadenas de proveedores y dos políticas de seguridad.

El orquestador de Vigilancia usa `CONJUNTO_AI_URL` para solicitar asesoría al endpoint `/analyze/surveillance_advisor`. La IA recibe evidencia de sensores, cámaras y telemetría, pero no herramientas de control físico.

### Operación sin coste de API

- `deterministic`: siempre disponible para pruebas/offline.
- `ollama`: modelo local, sin consumo de API externa; requiere CPU/GPU y almacenamiento local.
- OpenAI, Gemini y Anthropic son opcionales y se habilitan mediante `AI__LLM_ALLOWED_PROVIDERS` + credenciales.

### Equipos

ESP32, sensores de barrera, tamper, cámaras y drones se mantienen como subsistemas de Vigilancia. El `EquipmentRegistry` permanece fail-closed y el LLM no puede ejecutar comandos físicos.
