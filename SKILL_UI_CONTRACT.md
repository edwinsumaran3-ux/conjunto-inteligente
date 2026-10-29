# Contrato de Skill UI — Conjunto Inteligente

Este contrato se propone como puerta obligatoria para cualquier skill o agente expuesto al usuario.

## Contrato mínimo

```yaml
skill_id: diagnostic.asset.health
version: 1.0.0
risk: advisory # advisory | operational | critical
input_schema: json-schema-uri-or-inline
output_schema: json-schema-uri-or-inline
required_scopes:
  - assets.read
  - telemetry.read
tenant_scoped: true
timeout_seconds: 20
idempotency_required: true
human_approval: false
side_effects: []
evidence_required: true
```

## Reglas

- Validar entradas y salidas contra esquemas versionados.
- Denegar por defecto si faltan tenant, scopes, evidencia o límites.
- Las skills críticas (control físico, accesos, compra, contratación, pago, eliminación) requieren aprobación humana explícita y auditoría.
- Cada resultado debe separar `observations`, `inferences`, `recommendations` y `actions`; incluir fuente, hora, confianza y versión del modelo/regla.
- Los reintentos deben ser idempotentes. Los fallos parciales deben exponer estado y compensación, no ocultarse.
- Los datos faltantes/obsoletos deben producir `UNKNOWN`/`STALE`, nunca `HEALTHY` por defecto.
- La UI no puede afirmar que se ejecutó una acción hasta recibir confirmación del servicio y su identificador de auditoría.
- Las skills no deben recibir secretos de infraestructura ni poder consultar otros tenants.
- Evaluar cada versión con casos normales, límites, entradas maliciosas, falta de datos, timeout y regresión.
