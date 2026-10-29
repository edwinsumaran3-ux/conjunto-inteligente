# Auditoría de causa raíz y correcciones de punta a punta

Fecha de ejecución: 2026-10-11

## Alcance real

Se inspeccionó el paquete fusionado v5, se ejecutaron las suites Python disponibles y se corrigieron fallos reproducibles en la rama canónica `b09work`. Se conservaron las carpetas históricas y variantes recuperadas; no se sobrescribieron silenciosamente las versiones archivadas.

## Causas raíz encontradas y corregidas

1. **Verificador de punta a punta roto por rutas antiguas.** `scripts/verificar_todo.sh` intentaba escribir en `docs/` sin crearla y apuntaba a `apps/web-admin/frontend/web-admin`, `ConjuntoInteligente/` y otras rutas que no existen en este paquete recuperado. Ahora crea el directorio, usa las rutas existentes, ejecuta las suites que sí están presentes y marca como omitidas (no aprobadas) las verificaciones que dependen de herramientas/infraestructura ausentes.
2. **Auditoría estática fallaba si `docs/` no existía.** `scripts/auditoria_estatica.py` ahora crea el directorio de salida antes de guardar el informe.
3. **Configuración pytest inconsistente.** El ERP tenía imports legacy `app.*` y `backend.app.*` y varios módulos de prueba con nombres repetidos. `pytest.ini` ahora expone ambos roots (`. backend`) y usa `--import-mode=importlib`, evitando el error de colección y manteniendo las importaciones compatibles.
4. **Idempotencia del outbox del gemelo digital rota.** El endpoint consultaba `outbox_events.topic`, pero el esquema real define `event_type`; la búsqueda tampoco restringía `aggregate_type`. Se corrigió para consultar `event_type`, `aggregate_type` y el agregado correspondiente.
5. **Registro de métricas duplicado al cargar el worker más de una vez.** El worker de vigilancia registraba counters en el registro global de Prometheus, causando `Duplicated timeseries` en los tests/harnesses. Ahora utiliza un `CollectorRegistry` propio y el endpoint de métricas exporta ese registro.
6. **Suite de vigilancia lanzada en un único proceso con imports planos en colisión.** Las suites de `tests/` y `services/agent-orchestrator/tests` importan módulos llamados `models`; combinarlas en una sola invocación hacía que Python reutilizara el módulo equivocado. El `Makefile` y el verificador ahora ejecutan ambas suites en procesos separados.
7. **CI de GitHub apuntaba a componentes que no existen en la distribución recuperada.** El workflow intentaba compilar una solución .NET, frontend admin y app móvil en rutas ausentes, además de invocar una prueba de base de datos que referencia migraciones no presentes. Se sustituyó por trabajos con rutas reales: ERP Python, agentes IA, frontend ERP existente, vigilancia con PostgreSQL y gateway C++.

## Validaciones ejecutadas después de las correcciones

| Validación | Resultado |
|---|---:|
| Pruebas de módulos ERP Python | 146 aprobadas |
| Pruebas del agente IA | 24 aprobadas |
| Pruebas de vigilancia | 42 aprobadas |
| Pruebas del orquestador de agentes de vigilancia | 4 aprobadas |
| Total de pruebas Python ejecutadas en estas suites | 216 aprobadas |
| Verificación estructural de vigilancia | PASS: 76 archivos Python, 8 migraciones, 22 tablas declaradas |
| Auditoría estática Python/imports/migraciones | PASS |
| ZIP original de salida | Integridad CRC verificada tras creación |

## Verificaciones no ejecutadas: no deben confundirse con aprobadas

- **Frontend:** no se pudo instalar dependencias en este entorno; `npm install` agotó el tiempo límite y no hay `node_modules`/`pnpm`. No se certificó typecheck ni build.
- **.NET:** el SDK no está instalado y esta distribución no contiene `ConjuntoInteligente.sln` en la ruta esperada. El build .NET no se certificó.
- **PostgreSQL/RLS real:** no se configuró `DATABASE_URL` para el verificador local. El workflow CI sí contiene un servicio PostgreSQL para la suite de vigilancia, pero no se ejecutó GitHub Actions desde este entorno.
- **Edge C++:** el código de gateway requiere CMake 3.28+, Paho MQTT, OpenSSL, SQLite y dependencias FetchContent. No se compiló aquí.
- **Hardware, MQTT/PKI, OIDC, almacenamiento de objetos y despliegue:** requieren infraestructura y secretos externos que no están disponibles en esta sesión.

## Estado y recomendación

Se corrigieron fallos reproducibles de harness, rutas, configuración de pruebas, consulta de idempotencia y registro de métricas. Las 216 pruebas Python indicadas pasan en el entorno local. Esto **no equivale a certificar toda la plataforma en producción**: las áreas omitidas siguen abiertas y se señalan expresamente. El ZIP conserva las variantes históricas para no perder material; la ruta canónica de trabajo es `ConjuntoInteligente_COMPLETO_FUSIONADO_BIM_GEMELO/b09work/`.
