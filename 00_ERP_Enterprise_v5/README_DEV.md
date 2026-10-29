# Conjunto Inteligente · entorno local

## Servicios

- API FastAPI: `http://127.0.0.1:8000`
- Visor BIM servido por la API: `http://127.0.0.1:8000/bim/`
- PostgreSQL instalado en Windows: `127.0.0.1:5433`, base `conjunto_inteligente_dev`
- Redis: contenedor privado del stack, sin puerto publicado en Windows

La API usa la base aislada `conjunto_inteligente_dev`; no usa ni modifica `gabis_boutique_django`. El Postgres es externo a Docker y no se levanta otro contenedor PostgreSQL.

## Dashboard

El inicio (`http://127.0.0.1:8000/`) sirve el centro de mando; el visor BIM permanece en `http://127.0.0.1:8000/bim/`. Ambos consumen la misma sesión de tenant y el dashboard presenta métricas reales de la API, sin rellenar datos faltantes. Desde el centro de mando se puede navegar el inventario paginado de activos, puntos de telemetría, versiones IFC y anomalías. El flujo de diagnóstico y las solicitudes de mantenimiento siguen gestionándose desde el visor; la interfaz distingue las solicitudes propuestas de las órdenes aprobadas o ejecutadas.

La carga de modelos IFC conserva su flujo existente. Un archivo IFC puede aportar geometría, clasificación, jerarquía y propiedades; la plataforma muestra únicamente la información que se pudo validar e importar. Planos 2D no se convierten automáticamente en geometría BIM. El laboratorio de sensores virtuales permite probar telemetría y diagnóstico sin hardware; las lecturas IoT/BMS físicas siguen requiriendo integrar y validar su sistema de origen.

Para desarrollar el dashboard y el visor BIM en Vite, mantén la API iniciada y ejecuta desde `frontend`:

```powershell
npm ci
npm run dev:stack
```

El comando inicia en conjunto el dashboard (`http://127.0.0.1:5173/`) y el visor BIM (`http://127.0.0.1:5174/bim/`). El enlace BIM del dashboard usa la ruta `/bim/` del mismo origen y Vite la reenvía al servidor BIM; si cualquiera de los procesos no puede iniciarse en su puerto esperado, el comando informa el fallo en lugar de dejar un enlace roto.

Dashboard y BIM resuelven la API desde la URL guardada en `sessionStorage["bim.api"]`, o desde `VITE_API_BASE_URL` si no hay una URL guardada. Si ambas están vacías, usan el mismo origen: en desarrollo, Vite reenvía `/api` a `http://127.0.0.1:8000`; en el servicio empaquetado, la API y las interfaces comparten origen.

El dashboard y el visor BIM comparten la sesión temporal `ci.auth-session` en `sessionStorage`; las claves antiguas `bim.tok`, `bim.tenant` y `bim.email` se migran al leerla. Las llamadas autenticadas no usan caché HTTP y la API responde `Cache-Control: no-store`, para impedir que una respuesta válida de una sesión anterior se reutilice para otro token. Al iniciar sesión se valida el token contra un endpoint protegido antes de guardarlo como sesión activa. Los JWT duran 15 minutos por defecto; no existe renovación automática, por lo que un token vencido requiere volver a iniciar sesión.

## Arrancar

Desde esta carpeta:

```powershell
docker compose -f compose.dev.yml up -d --build api
```

Compose construye la imagen, verifica/aplica migraciones y espera a Redis antes de iniciar la API. Comprobar estado:

```powershell
docker compose -f compose.dev.yml ps
Invoke-RestMethod http://127.0.0.1:8000/healthz
Invoke-RestMethod http://127.0.0.1:8000/readyz
```

El tenant local y el usuario de acceso están en `C:\Users\LasPa\AppData\Local\ConjuntoInteligente\dev-admin.txt`. Ese archivo contiene el correo y el tenant, no la contraseña. No hay que añadir `.env` ni credenciales al repositorio.

La base nueva empieza vacía. El IFC demo se sirve desde la app, pero el dashboard mostrará cero nodos, puntos y modelos hasta importar o registrar datos. Después de crear nodos del gemelo, el laboratorio permite asociar sensores virtuales a ellos. Los datos se identifican explícitamente como sintéticos y no representan mediciones de campo.

## Órdenes de mantenimiento, residentes y proveedores

La migración `0013_maintenance_operations` agrega perfiles de residentes vinculados a usuarios existentes, asignaciones históricas de unidades, proveedores y órdenes operativas. Las tablas nuevas aplican RLS con `app.current_tenant_id`; el readiness exige las tablas principales de esta fase.

Después de actualizar el código, aplica migraciones con `alembic upgrade head` desde `00_ERP_Enterprise_v5`. Rutas principales bajo `/api/v1`:

- `GET/POST /maintenance/orders`, `GET /maintenance/orders/{id}` y `GET /maintenance/orders/{id}/events`.
- `POST /maintenance/orders/{id}/approve` requiere `expected_version` y rol gestor; una propuesta se aprueba explícitamente a `scheduled`.
- `PATCH /maintenance/orders/{id}/status` valida transiciones y versión esperada; los cambios quedan en un historial append-only y en `audit_log`.
- `PATCH /maintenance/orders/{id}` actualiza proveedor, costo, SLA o descripción con control optimista de versión.
- `GET /maintenance/units` publica el catálogo tenant-scoped y paginado que usa la asignación de residentes.
- `GET/POST /maintenance/residents`, `GET/PUT /maintenance/residents/{id}` y `GET/POST/PUT /maintenance/vendors`.
- `GET /tenants/current` devuelve solo el tenant del JWT actual; no expone un listado global de tenants.

El panel de mantenimiento ofrece consulta paginada de unidades, residentes y proveedores a gestores, y formularios de alta/edición solo cuando la API confirma permisos administrativos. Los residentes se enlazan a usuarios activos ya existentes y a unidades del tenant; la API conserva el historial de asignaciones. Un usuario regular solo puede crear una orden vinculada a su perfil residente activo; un gestor puede crearla para otro residente. El NIT es único por tenant. La vigencia documental del proveedor se calcula desde la fecha declarada `documents_valid_until` y no equivale a verificar archivos oficiales; la calificación es un valor administrado, no un promedio derivado. El ERP no tiene contabilidad residencial de saldos, por lo que `saldoCop` se devuelve como `null` en el bridge, nunca como cero inventado.

## Redes MEP

El visor lee `IfcDistributionSystem`/`IfcDistributionCircuit`, miembros de `IfcRelAssignsToGroup` y conexiones IFC directas o entre puertos. Las capas Agua, Gas, Eléctrico, HVAC e Incendio solo se habilitan cuando hay componentes asignados a un sistema reconocible; tramos genéricos sin clasificación quedan como no clasificados. El color de salud del backend prevalece sobre el color de disciplina.

El IFC demo incluido no declara sistemas MEP, segmentos de tubería ni cables. Por eso muestra cero sistemas/conexiones y sus dos equipos sin clasificación. Para visualizar una distribución real, el IFC cargado debe contener la geometría y las relaciones de grupo/conexión; los sensores físicos deben enlazarse a nodos y puntos del gemelo. El laboratorio virtual puede generar lecturas sintéticas para probar el procesamiento, pero nunca inventa geometría, recorridos ni datos físicos.

## Laboratorio IoT sin hardware

En **Sensores y señales**, crea un sensor virtual asociado a un nodo existente y ejecuta una lectura normal o una alarma de prueba. Cada ejecución genera cinco muestras reproducibles a partir de una clave de idempotencia, se procesa por el mismo endpoint de ingesta y queda marcada `data_origin=simulated`. Las ejecuciones de alarma pasan por el diagnóstico determinista existente y pueden generar anomalías visibles en **Incidencias y mantenimiento**; no crean órdenes ejecutadas ni envían comandos a equipos.

Para integraciones de pasarela, `POST /api/v1/digital-twin/telemetry/samples/batch` acepta lotes atómicos de hasta 500 lecturas con identificadores de mensaje idempotentes. Las pasarelas físicas pueden usar `POST /api/v1/edge-transport/telemetry/batch`, que exige firma Ed25519, anti-replay y asignación del gateway a un nodo BIM; solo admite puntos de ese nodo o sus descendientes. El endpoint físico fuerza metadatos de procedencia del servidor y aplica límites transaccionales compartidos entre instancias: 120 solicitudes y 10 000 muestras por minuto por gateway de forma predeterminada; los límites se configuran con `EDGE_TELEMETRY_MAX_REQUESTS_PER_MINUTE` y `EDGE_TELEMETRY_MAX_SAMPLES_PER_MINUTE`. Si se supera el presupuesto responde `429` e incluye `Retry-After`. El anti-replay conserva un watermark monotónico por gateway y purga en lotes acotados el historial de nonce vencido a 30 días. MQTT y brokers no están implementados.

### Pruebas contra PostgreSQL real

Las pruebas en `backend/tests/integration` reinicializan `public` con `DROP SCHEMA public CASCADE`; nunca las apuntes a la base de desarrollo compartida ni a producción. El harness ahora exige que el nombre de la base incluya un segmento `test`, `testing`, `e2e` o `ci` y que se configure explícitamente `PHASE13_ALLOW_DATABASE_RESET=1`. Conserva las credenciales en variables locales y no las publiques:

```powershell
$env:PHASE13_DATABASE_URL = "postgresql+asyncpg://<usuario>:<clave>@<host>:<puerto>/<base_e2e_test>"
$env:PHASE13_ALLOW_DATABASE_RESET = "1"
$env:PYTHONPATH = "backend"
.\\.venv\\Scripts\\python.exe -m pytest backend\\tests\\integration --import-mode=importlib -q
```

La prueba `test_maintenance_postgres_e2e.py` valida con PostgreSQL real la creación de residentes/proveedores y órdenes, el bloqueo de solicitudes a unidades no asignadas, aprobación/transiciones con control de versión, aislamiento tenant y la inmutabilidad del historial. El test crea su esquema desde cero, por lo que requiere un clúster/base de pruebas desechable y no debe apuntarse al PostgreSQL local de desarrollo.
El panel web de mantenimiento muestra anomalías, propuestas BIM y órdenes operativas por separado. Los residentes pueden registrar y consultar sus propias solicitudes; los gestores ven la cola general y pueden aprobar o transicionar órdenes. La API sigue siendo la autoridad de permisos y versiones. Para probar el flujo E2E desde la raíz del proyecto usa `make test-maintenance` solo después de configurar las dos variables de confirmación anteriores.

El workflow raíz de GitHub Actions dispone de un job independiente `erp-postgres-integration` que provisiona PostgreSQL 16 en el runner efímero y ejecuta la suite completa de `backend/tests/integration` sobre una base de nombre `erp_backend_ci_test`; la confirmación destructiva solo se configura para ese servicio descartable. También ejecuta build/test de la API central .NET y del bridge PowerBuilder, además de pruebas nativas del firmware. La configuración del workflow no equivale a una ejecución aprobada: revisa el resultado de cada job en Actions después de subir los cambios.

`test_deploy_migrations.py` también aprovisiona el rol global `erp_app` y cambia su contraseña de prueba; ejecuta la suite solo en un clúster PostgreSQL de pruebas dedicado, o después de aislar/provisionar un rol de aplicación exclusivo para pruebas.

La guía de uso, contratos y límites está en [`docs/IoT_SIMULATOR.md`](docs/IoT_SIMULATOR.md). El PDF de arquitectura y auditoría se conserva dentro del proyecto en [`docs/Conjunto_Inteligente_Arquitectura_y_Auditoria.pdf`](docs/Conjunto_Inteligente_Arquitectura_y_Auditoria.pdf). La simulación valida software e integración; no certifica sensores, calibración, cobertura de radio ni seguridad física. El transporte HTTPS autenticado valida la identidad de la pasarela y el ámbito de los puntos; la puesta en servicio física aún requiere integración del sistema de origen, calibración y pruebas de campo. MQTT no está implementado.

## Parar

```powershell
docker compose -f compose.dev.yml stop
```

Esto detiene solo los servicios `conjunto-inteligente-*`. No usar `docker compose down -v`: el volumen Redis pertenece a este proyecto y no hace falta borrarlo para trabajar en nuevas fases.