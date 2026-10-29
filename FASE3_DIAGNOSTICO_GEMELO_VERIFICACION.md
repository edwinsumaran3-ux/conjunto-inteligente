# FASE 3 — Diagnóstico de ingeniería y Health del Gemelo

Fecha: 2026-10-05

## Objetivo

Elevar el Gemelo Digital desde telemetría operacional a diagnóstico auditable, sin crear un segundo ciclo de anomalías.

## Integración

`Twin Point -> telemetry samples -> robust baseline -> deviation/trend/persistence/quality -> impairment -> health -> severity -> probable causes -> operational_anomalies/autonomous plane`

## Componentes nuevos

- `backend/app/modules/digital_twin/domain/diagnostic_engine.py`
- `backend/app/modules/digital_twin/tests/test_diagnostic_engine.py`
- `backend/migrations/versions/0055_twin_diagnostics_health.py`
- endpoint `POST /digital-twin/diagnostics/evaluate`

## Persistencia

- `twin_diagnostic_runs`
- `twin_diagnostic_features`
- `twin_health_assessments`
- `twin_anomaly_correlations`
- extensión de `operational_anomalies` con vínculo al punto y ejecución diagnóstica

## Ingeniería aplicada

- Mediana + MAD para baseline robusto.
- Escala mínima limitada por rango de ingeniería cuando existe.
- Deviation, trend y persistence separados como features auditables.
- Penalización explícita de calidad de dato.
- Health 0–100 y severidad determinista.
- Causas probables, no afirmaciones de causa raíz física.
- Evidencia persistida para reproducibilidad.

## Corrección preventiva

`0053_engineering_digital_twin_foundation.py` contenía dos columnas llamadas `state` en `twin_state_snapshots` (`varchar` y `jsonb`), lo que impediría ejecutar esa migración en PostgreSQL. Se eliminó únicamente la definición duplicada `jsonb`; se conserva el campo de estado textual y `state_data` como payload estructurado.

## Validación ejecutada

- `pytest`: **8/8 PASS** para diagnóstico y telemetría pura.
- `py_compile`: **PASS** para router, motor y migraciones 0053–0055.
- Migración 0055: cadena declarada sobre 0054.
- Suite completa que importa el router: **NO EJECUTADA**, porque el entorno no tiene `pwdlib`, dependencia del ERP (`ModuleNotFoundError: pwdlib`).
- PostgreSQL real / RLS / ejecución Alembic: **NO VERIFICADO** en este entorno.
- MQTT/OPC-UA/BMS/SCADA: **NO IMPLEMENTADO EN ESTA FASE**.
- ML/IA causal: **NO SE DECLARA IMPLEMENTADO**; el motor es determinista y auditable.

## Regla de honestidad

Un `PASS` solo representa una prueba realmente ejecutada. Lo demás permanece como `NO VERIFICADO` o `NO IMPLEMENTADO`.
