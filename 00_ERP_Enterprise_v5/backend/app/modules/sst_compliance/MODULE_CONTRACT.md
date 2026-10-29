# sst_compliance — contrato del módulo

Implementa la especificación «Arquitectura Integral BIM · Gemelo Digital · ERP · SST · Cadena de Suministro» (v1.0, 11-oct-2026) dentro del ERP FastAPI. **No duplica** TOTP/step-up, `audit_log` ni idempotencia: los reutiliza.

## Reglas no negociables (cubiertas por pruebas de dominio)
- **Falla segura**: sin reglas aprobadas, sin evidencia, sin vigencia declarada, dato faltante o fuente caída ⇒ nunca `cumple`.
- **El silencio jamás aprueba**: una aprobación sin decisión pasa a `expired` y la actividad queda bloqueada.
- **Token**: aleatorio (48 B), solo se guarda su SHA-256, un solo uso (consumo atómico `UPDATE … WHERE used_at IS NULL`), ligado a aprobación + destinatario + acción + versión, TTL ≤ 60 min y ≤ vencimiento de la aprobación. MFA obligatorio según matriz/riesgo.
- **Sin autoaprobación**: `requester ≠ aprobador` en dominio **y** en CHECK de BD.
- **Los agentes proponen, no deciden**: cantidad/tipo requerido vienen de una regla aprobada; si no hay, la cobertura es `desconocida`. Una asignación temporal solo cuenta tras verificación física por otra persona.
- **Auditoría**: `audit_log` (append-only, existente) + `sst_audit_chain` (hash por tenant, serializada con advisory lock, verificable en `GET /sst/audit/verify`).

## Endpoints (`/api/v1/sst/*`)
`POST activities` · `POST activities/{id}/evaluate` · `GET activities/{id}/requirements` · `GET activities/{id}/coverage` · `POST approvals` · `POST approvals/{id}/decision` · `POST approvals/expire-due` · `POST work-permits/{id}/activate` · `POST temporary-assignments` · `POST temporary-assignments/{id}/verify` · `GET audit/verify` · `GET|POST webhooks/meta`.

## Estado honesto
| Nivel | Estado |
|---|---|
| Dominio (reglas, autoridad, aprobaciones, permiso/ATS, cobertura, cadena, webhook) | **VALIDADO**: `python3 scripts/run_sst_tests.py` (stdlib) + prueba de mutación |
| `application/service.py`, `api/router.py`, migración `0062` | **COMPILAN**; **NO ejecutados** contra PostgreSQL/FastAPI (sin red ni dependencias en el entorno de construcción) |
| RLS cross-tenant, API HTTP, Meta/WhatsApp real, OIDC | **NO VERIFICADO** |

## Pasos exactos para verificar (CLAUDE.md regla 10)
1. `pip install -r requirements.lock && pytest backend/app/modules/sst_compliance/tests`
2. PostgreSQL 16: `alembic upgrade head` (debe terminar en `0062_sst_compliance`) y `alembic downgrade 0061_bim_geometry_spatial && alembic upgrade head`.
3. Prueba cross-tenant: con `app.tenant_id` = A, `SELECT` de filas de B en cada tabla `sst_*` debe devolver 0 y un `INSERT` con tenant B debe fallar.
4. Confirmar que `UPDATE/DELETE` sobre `sst_audit_chain` y `DELETE` sobre `sst_evidence` fallan.
5. Meta: configurar `WHATSAPP_APP_SECRET` y `WHATSAPP_VERIFY_TOKEN`; el envío debe incluir `biz_opaque_callback_data="<tenant_id>:<attempt_id>"`.

## Pendiente (no construido aquí)
Canal de salida que entregue el token (WhatsApp/correo/SMS), worker programado de `expire_due` y reintentos, generador/firmas de ATS en UI, cola de revisión OCR, acceso de contratistas, frontend (bandeja de aprobaciones, centro de cumplimiento), enlace RFQ/PO .NET ↔ aprobaciones, módulos `assets`/`maintenance`. **Las reglas SST/normativas las carga y aprueba un profesional competente**: sin ellas el sistema bloquea por diseño.
