# 10 — Fusión con VigilanciaPlatform (.NET) en un solo repositorio

## Contexto

Durante esta iteración se recibieron dos entregables con el mismo dominio (vigilancia
distribuida) pero **arquitecturas de ejecución incompatibles**:

| | Este repositorio (base operativa) | `VigilanciaPlatform-v2.2/2.3/2.4` (.NET) |
|---|---|---|
| Backend | Python 3.12 / FastAPI / asyncpg / aio-pika | C# / ASP.NET Core |
| Frontend | React + TypeScript + Vite | JavaScript plano (Operations Portal) |
| Estado | 155+ archivos, microservicios funcionando end-to-end | ~109 archivos, mayoría de 200–1500 bytes: contratos, interfaces y documentos de un **esqueleto "conservation-first"**, con pruebas marcadas `NOT RUN` (requieren SDK .NET, IdP real, hardware) |
| Mensajería | RabbitMQ | Kafka/MQTT/NATS (documentado, no implementado) |

No existe una forma honesta de "fusionar" dos runtimes distintos línea por línea sin
generar código muerto (C# que ningún proceso ejecuta) o duplicar por completo la
plataforma en dos lenguajes. La decisión, confirmada por el usuario, fue:

**Fusión = un solo repositorio operativo (Python/FastAPI + React), incorporando las
piezas de mayor valor del esqueleto .NET traducidas a este stack.** El ZIP `.NET`
original no se descarta: sus documentos de arquitectura siguen siendo la referencia de
las correcciones semánticas que se adoptaron aquí.

## Qué se portó (implementado en este repositorio)

| Capacidad en VigilanciaPlatform (.NET) | Dónde quedó en este repositorio |
|---|---|
| `SecurityHeadersMiddleware.cs` (CSP, X-Frame-Options, etc.) | `shared/security/security_headers_middleware.py` + copia local en `ingestion`, `edge-gateway`, `agent-orchestrator` |
| `CorrelationIdMiddleware.cs` | `shared/security/correlation_id_middleware.py` + copias locales, cableado en los mismos tres servicios |
| `TenantAuthorization.cs` + corrección "no confiar en el tenant-header del cliente" | `shared/security/tenant_context.py` — **frontera operacional explícita**: mientras no haya IdP/JWT real conectado, siempre resuelve `default-tenant` y documenta el punto de extensión; nunca confía en un header sin verificar |
| `IEquipmentAdapter.cs` / `EquipmentRegistry.cs` (comando firmado, nonce anti-repetición, expiración, `EmergencyStop`) | `services/agent-orchestrator/src/equipment_contracts.py` + `equipment_registry.py` |
| `Adapters/*Boundary.cs` (dron, PTZ, robot terrestre, IR) fail-closed | `services/agent-orchestrator/src/equipment_adapters/*_boundary.py` — el adaptador PTZ es la única frontera con actividad real: el reencuadre digital por cascada (`FOCUS_CAMERA` vía MQTT) ya funciona; el movimiento físico del motor sigue bloqueado sin SDK ONVIF |
| `docs/security/frontend-and-api-hardening.md` + `security-smoke.mjs` | `dashboard/index.html` (meta CSP) + `dashboard/tests/security-smoke.mjs` |
| `tests/security/security-regression.py` | `tests/test_security_regression.py` |
| Endpoint de estado de equipos + parada de emergencia | `GET /equipment/registry`, `POST /equipment/emergency-stop` en `agent-orchestrator`, expuestos en el dashboard vía `EquipmentRegistryPanel` |

## Qué se preserva como corrección semántica (documentada, no solo código)

Las cinco "IMPORTANT SEMANTIC CORRECTIONS" del baseline .NET ya eran o pasaron a ser
ciertas en este repositorio:

1. **At-least-once + idempotencia**, no exactly-once global: `services/ingestion/src/idempotency.py` ya implementaba esto antes de la fusión.
2. **Fail-safe físico del IR local al controlador**, independiente del software central: el sensor láser/IR de *detección* (`firmware/esp32-edge/src/laser_sensor.cpp`) ya es local; el nuevo `IrActuatorAdapterBoundary` refuerza que ningún *actuador* IR se dispara sin verificación de firma real, todavía no conectada.
3. **Kafka/MQTT/NATS no son intercambiables**: este repositorio usa un único bus (RabbitMQ) documentado por clase de tráfico en `docs/01-arquitectura.md`; no se adoptó Kafka/NATS del .NET porque habría significado una reescritura de mensajería sin beneficio funcional adicional.
4. **La IA nunca escribe directo en tablas de dominio**: `services/vision-ai` ya publica eventos, no escribe SQL directo.
5. **RTO/RPO son objetivos, no compromisos**, hasta validarse con simulacros reales: ya explicitado en `docs/05-production-checklist.md`.

## Qué NO se portó, y por qué

- **Kafka / NATS / Schema Registry / Event Sourcing / CQRS / Saga**: el pipeline RabbitMQ
  fanout + colas priorizadas ya cumple los requisitos actuales de este sistema (ver
  `docs/01-arquitectura.md`). Adoptarlos sería una reescritura de infraestructura sin
  una necesidad funcional identificada todavía.
- **Terraform / Kubernetes / Service Mesh / Vault / OPA**: este repositorio despliega
  con `docker-compose` para desarrollo/integración (`infrastructure/docker-compose.yml`).
  Los manifiestos de Terraform/K8s del .NET son un buen punto de partida para un
  despliegue productivo futuro, pero no se tradujeron porque no hay todavía un target
  de nube/clúster definido por el usuario.
- **RLS multi-tenant en PostgreSQL**: no se migró el esquema para aislar tenants por
  fila porque, sin un IdP real resolviendo `tenant_id` de forma verificable
  (ver `tenant_context.py` arriba), añadir RLS habría sido una promesa de aislamiento
  que el sistema no podría cumplir todavía. Es la misma razón por la que el propio
  repositorio .NET marca "Database RLS integration: NOT RUN" en su matriz de validación.
- **Mobile App / Admin Portal / Design System separado**: no existían implementados en
  ninguno de los dos ZIPs (solo mencionados en el inventario de capacidades del .NET);
  no se inventó nada nuevo para mantener la regla de "agregar sin fingir".
- **Reescritura del frontend a JavaScript plano**: el `OperationsPortal` .NET es
  deliberadamente más simple (sin build step); el dashboard React/TS de este
  repositorio ya es más capaz (grid de cámaras, topología, agentes) y se mantuvo como
  base única en vez de duplicar la UI en dos frameworks.

## Matriz de validación de la fusión

| Verificación | Resultado |
|---|---|
| Sintaxis Python de todos los módulos nuevos/editados (`py_compile`) | PASS |
| `dashboard/tests/security-smoke.mjs` | PASS |
| `tests/test_security_regression.py` | PASS |
| Compilación TypeScript (`tsc --noEmit`) | Validado con stubs mínimos de tipos (sin `@types/react` reales, sin red disponible); 2 bugs reales encontrados y corregidos (ver historial), resto son falsos positivos de los stubs |
| Integración end-to-end con `docker compose up` | NO EJECUTADO — requiere el entorno destino |

## Auditoría de consistencia post-fusión

Tras conectar `EquipmentRegistry` al repositorio, se encontraron y corrigieron dos
inconsistencias reales entre lo agregado en distintos turnos:

1. **`EquipmentRegistry` desconectado del despacho real**: el loop de agentes
   (`agent_loop.py`) seguía publicando todas las acciones directo por
   `ChainCommunicator`/MQTT, sin pasar nunca por el registro con nonce/firma/fail-closed
   — es decir, si una acción hubiera apuntado a `drone-01`, el adaptador fail-closed
   nunca la habría interceptado. Se corrigió agregando `AgentOrchestratorLoop._dispatch()`
   como único punto de salida: si `target_device_id` corresponde a un equipo dado de
   alta en el registro, pasa obligatoriamente por `EquipmentRegistry.dispatch()`
   (construyendo un `EquipmentCommand` con nonce; la firma placeholder antigua
   `"system-issued:unverified"` es rechazada explícitamente por `EquipmentRegistry`); el resto de dispositivos
   (cámaras, sensores) sigue por `ChainCommunicator` como antes. El resultado del
   adaptador (aceptado/rechazado) ahora se persiste en `agent_actions.status`.
2. **Documentación desactualizada**: el docstring de `PerimeterAgent` apuntaba a
   `chain_communicator.py` como dueño de la topología de malla; la malla real vive en
   `edge-gateway/src/sensor_mesh.py` (autonomía de borde). Se corrigió el docstring y
   se eliminó `ChainCommunicator.cascade_focus()`, un método que nunca se invocaba
   desde ningún lugar (código muerto que sugería una ruta de cascada centralizada que
   en realidad no existe).
