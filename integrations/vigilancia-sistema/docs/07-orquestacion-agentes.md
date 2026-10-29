# 07 — Orquestación de agentes autónomos

## Ciclo Sense → Plan → Action Proposal → Reflect

Implementado en `services/agent-orchestrator/src/agent_loop.py`:

- **Sense**: consumo continuo de `incidents.fanout` (RabbitMQ), ya emitidos por
  `correlation-engine` a partir de eventos de sensores/cámaras/láser-IR.
- **Plan**: cada agente especializado (`agents/`) evalúa si el incidente le concierne
  y, si corresponde, produce una `ActionProposal`.
- **Action Proposal**: se persiste en `agent_actions`; si no requiere aprobación
  humana se despacha de inmediato vía `ChainCommunicator`; si la requiere, entra a la
  cola de `HumanValidationGate`.
- **Reflect**: cada `tick_s` segundos se barren aprobaciones vencidas
  (`sweep_expired`) y se aplica el `fallback_action` configurado en vez de la acción
  original.

## Agentes especializados

| Agente | Incidentes que evalúa | Acciones que puede proponer |
|---|---|---|
| `IntrusionAgent` | `TAMPER`, `INTRUSION`, `MOTION_BURST` | `SOUND_ALARM`, `LOCK_ACCESS`, `START_RECORDING` |
| `PerimeterAgent` | `PERIMETER_BREACH` (barreras láser/IR) | `FOCUS_CAMERA` (cascada, sin aprobación humana) |
| `HardwareIntegrityAgent` | `DEVICE_TAMPERING`, `CAMERA_FAILOVER`, `HEARTBEAT_LOST` | `NOTIFY_AUTHORITIES`, `SAFE_HOLD` |

Ningún agente ejecuta directamente: solo propone (`assess` devuelve `ActionProposal
| None`). La ejecución siempre pasa por `HumanValidationGate` (si requiere aprobación)
o `ChainCommunicator` (si es auto-aprobada por no ser destructiva).

## Validación humana (Human-in-the-Loop)

`human_validation.py` encola cada acción CRITICAL/HIGH con una ventana de expiración
(`APPROVAL_TIMEOUT_S`, 45–900s según severidad). El operador confirma o rechaza desde
`HumanApprovalModal` en el dashboard, autenticado por nombre (`decided_by`). Si vence
sin decisión, `agent_loop.run_forever()` aplica automáticamente el `fallback_action`
(por defecto `SAFE_HOLD`) — la orden original nunca se ejecuta por omisión.

## Comandos firmados a nivel de equipo (fusión con hardening .NET)

Para acciones sobre hardware físico específico (dron, PTZ, robot, actuador IR), el
registro de equipos (`equipment_registry.py`) exige además: nonce de un solo uso,
ventana de expiración propia del comando y `authorize()` por adaptador antes de
`execute()`. Ver `docs/10-fusion-unificacion-plataforma.md` para el detalle de este
componente, portado de VigilanciaPlatform (.NET).
