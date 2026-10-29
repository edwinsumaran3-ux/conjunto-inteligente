# 16 · Base de datos estructurada y robustez operativa

## 1. Esquema versionado (`infrastructure/postgres/migrations/`)
| Migración | Contenido |
|---|---|
| 0001_baseline | `init.sql` original, byte a byte (el archivo original se conserva). |
| 0002_tenancy_sites | `tenants`, `sites`, `zones`; `tenant_id` en tablas existentes (default `'default'`); triggers `updated_at`. |
| 0003_integrity_constraints | CHECK/FK (`NOT VALID`), índices parciales/BRIN, unicidad correcta de `(device_id, sequence_number)`. |
| 0004_reliability_tables | `event_outbox` (outbox transaccional), `dead_letter_messages`. |
| 0005_equipment_and_audit | `equipment`, journal de comandos **append-only**, `audit_log` con **cadena de hash**, `operators`. |
| 0006_incident_lifecycle | Reconocimiento/resolución, `incident_events`, `incident_timeline`, `notifications`, estados terminales. |
| 0007_ai_audit_roles_retention | Auditoría neural ampliada (tokens, coste, failover, veredicto del guard), `ai_provider_policies`, roles `vigia_rw`/`vigia_ro`. |
| 0008_validate_constraints | Valida las `NOT VALID` sobre datos históricos; avisa (no aborta) si hay filas que las violan. |

Reglas: las migraciones **no se editan una vez aplicadas** (checksum en `schema_migrations` + `CHECKSUMS.sha256`); son solo aditivas; cada una corre en una transacción; un advisory lock evita migraciones concurrentes.

```bash
DB_DSN=postgresql://… python infrastructure/postgres/migrate.py            # aplicar
python infrastructure/postgres/migrate.py --status                          # ver estado
python infrastructure/postgres/migrate.py --write-manifest                  # tras añadir una migración NUEVA
python infrastructure/postgres/schema_check.py                              # verificación estática (sin BD)
```
En Docker Compose el servicio `db-migrate` corre antes que cualquier servicio que use la BD.

## 2. Defectos reales corregidos
1. **edge-gateway**: `on_message` nunca se asignaba al cliente MQTT → los eventos de los ESP32 no se procesaban. Además se resuscribe en cada reconexión.
2. **edge-gateway**: `flush()` sobrescribía el buffer y perdía eventos añadidos durante el reenvío; ahora `DurableBuffer` (tope, fsync, prioridad, cuarentena de líneas corruptas/rechazadas).
3. **Idempotencia**: `UNIQUE(device_id, sequence_number)` descartaba en silencio los eventos internos con `sequence_number=0`; ahora el índice es parcial (`> 0`).
4. **Colas**: un mensaje inválido se reencolaba sin fin (`requeue=True`); ahora dead-letter persistente con 1 reintento para fallos transitorios. Nunca se pierde un mensaje si el dead-letter no se puede guardar.
5. **Outbox**: antes, si la publicación fallaba tras el commit, el evento/incidente no se republicaba; ahora se confirma en la misma transacción y un relay lo reintenta con backoff.
6. **Comandos físicos**: la firma estática del entorno nunca coincidía con el HMAC canónico (todo comando era rechazado); ahora se firma con la clave del equipo. Se pasó `EQUIPMENT_HMAC_KEYS_JSON` al orquestador en el compose (antes no llegaba).
7. **Journal**: rechazos tempranos quedaban en `RECEIVED`; un `nonce`/`command_id` repetido provocaba excepción o doble ejecución. Ahora `begin()` devuelve el resultado, el anti-replay sobrevive reinicios, y sin journal el comando se rechaza (fail-closed).
8. **Orquestador**: el loop de fondo moría ante una excepción (sin barrido de aprobaciones → sin fallback seguro); tareas sin referencia; un agente defectuoso bloqueaba a los demás; redelivery duplicaba propuestas/acciones físicas; aprobar y fallar al ejecutar devolvía 200.
9. **Correlación**: “intrusión” se declaraba con eventos separados hasta 120 s (la ventana es 30 s).
10. **Ingestion**: Redis síncrono bloqueaba el event loop; si Redis caía se rechazaban eventos (ahora PostgreSQL es la autoridad); payload acotado a 64 KiB; clave opcional `INGEST_API_KEY`.
11. **AI Orchestrator**: su Dockerfile no instalaba `numpy/cv2/shapely/trimesh/fitz` que `app.main` importa al arrancar.
12. **docker-compose**: los mapas `{interval:5s}` sin espacio se leían como claves únicas (healthchecks ignorados); normalizado.

## 3. Dependencias
`requirements.txt` fijado por servicio (los Dockerfiles ya no duplican versiones inline), `constraints.txt` único, `requirements-dev.txt` (pytest, ruff, mypy, bandit, pip-audit). Pruebas verifican que todo esté fijado con `==`, que nada contradiga `constraints.txt` y que cada servicio declare lo que importa. El AI Orchestrator añade `requirements-llm.txt` (proveedores comerciales, opcional) y `requirements-neural.txt`.

## 4. Qué NO está verificado aquí
- Las migraciones **no se ejecutaron contra un PostgreSQL real** (no hay en este entorno): solo análisis estático + pruebas de lógica. El job `vigilancia` de CI las aplica en Postgres 16 y comprueba idempotencia; **ejecútelo antes de producción**.
- No se ejecutaron: RabbitMQ/Redis/MQTT reales, Docker E2E, `dotnet build`, `pnpm build`, ni las pruebas que requieren `pydantic`/`fastapi` instalados.
- Los adaptadores de fabricante siguen siendo fail-closed (`vendor transport not configured`).

## 5. Hoja de ruta
**Corto plazo:** ejecutar CI con Postgres real; provisionar claves HMAC por equipo en un gestor de secretos; activar `REQUIRE_AUTH_FOR_READS` y `INGEST_API_KEY`; que el dashboard envíe `X-Operator-Token`.
**Mediano:** sustituir el token único por identidad individual (`operators` ya existe) con firma de aprobación verificada; mover `incident_timeline`/`notifications` a los servicios; particionar `events` por mes cuando supere ~50 M filas; RLS por `tenant_id`; `statement_timeout` por rol.
**Largo:** PITR/réplicas de lectura, `pg_partman`, cifrado a nivel de columna para `payload`, adaptadores reales de fabricante con procedimiento de aceptación, pruebas de caos (partición de red, caída de broker/BD).
