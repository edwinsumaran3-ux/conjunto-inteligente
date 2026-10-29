# Reconciliación de Outbox — v9

## Hallazgo corregido

Las copias paralelas tenían contratos incompatibles para `outbox_events`: el árbol BIM usa `event_type`, `tenant_id UUID` y estados en minúscula; el árbol consolidado usa `topic`, `tenant_id TEXT`, estados en mayúscula y campos de despacho adicionales. Copiar su worker sin adaptar el esquema habría provocado errores SQL y no habría respetado correctamente la política RLS.

## Cambio de esta versión

- Se añadió `backend/app/core/outbox_worker.py`, alineado con el esquema del árbol BIM.
- El despacho exige un `tenant_id` UUID, filtra por ese tenant y establece `app.current_tenant_id` de forma local a cada transacción para respetar RLS.
- Se añadió la migración aditiva `migrations/sql/20261011_002_outbox_dispatcher.sql` para `available_at` y `locked_at` e índices parciales por tenant. No renombra ni elimina columnas existentes.
- Se añadieron pruebas de contrato y validación de parámetros.
- Las dos copias paralelas originales permanecen sin cambios; no se fusionó automáticamente código incompatible.

## Garantías y límites

La entrega es **at-least-once**, no exactly-once. Si el proceso cae después de publicar y antes de marcar `published`, el evento puede repetirse; el consumidor debe deduplicar usando `id`. Debe ejecutarse una instancia del worker por tenant autorizado. La migración no se ha aplicado contra una base PostgreSQL real en este entorno y aún requiere prueba de integración con RLS, broker real y consumidores idempotentes.
