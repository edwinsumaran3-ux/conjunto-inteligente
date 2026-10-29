# BLOQUE 02 — Producción: Digital Twin + Agent Control Plane

## Regla de preservación
Este bloque es aditivo. No se eliminó ningún archivo existente del bloque anterior. Se agregaron rutas, módulos, migraciones, contratos, tests y UI. Los archivos existentes corregidos conservan su función y se modificaron solo para conectar/validar comportamiento.

## Entregado

### Backend ERP
- `backend/app/modules/digital_twin/`
  - grafo multi-tenant
  - nodos físicos/operacionales
  - relaciones
  - telemetría
  - endpoints autenticados
  - validación de coordenadas
  - PostgreSQL RLS
- `backend/app/modules/agent_control/`
  - ledger durable de ejecuciones
  - memoria durable por agente
  - request/trace IDs
  - hash SHA-256 canónico de entrada
  - estado de ejecución y resultado/error
  - PostgreSQL RLS
- `migrations/versions/0039_digital_twin.py`
- `migrations/versions/0040_agent_control_plane.py`

### AI Agent
- contratos por agente con allowlist de herramientas
- separación read/write
- límites de contexto
- límites de llamadas
- herramienta permitida por agente + política global
- fail-closed si el agente no tiene la herramienta
- acciones consecuenciales mantienen aprobación humana

### Frontend
- nueva pantalla `/digital-twin`
- carga exclusivamente desde API
- jerarquía padre/hijo
- búsqueda
- estados reales devueltos por backend
- empty state explícito cuando no existe topología
- sin fabricar torres, apartamentos, sensores o métricas
- health endpoints corregidos a `/health/live` y `/health/ready`
- eliminación de valores numéricos inventados del asistente y del contador de WhatsApp

## Dependencias
Backend ERP: las dependencias existentes de `00_ERP_Enterprise_v5/pyproject.toml` siguen siendo la fuente de verdad. No se añadió una librería externa para Digital Twin ni Agent Control.

Frontend: se conserva la matriz existente de `package.json` y `pnpm-lock.yaml`. El entorno de validación de esta entrega no tuvo acceso al registro npm, por lo que no se declara un build TypeScript exitoso.

## Verificación ejecutada
- Python compileall del backend y AI: OK.
- ERP tests unit/security existentes: **57 passed**.
- AI service tests completos: **21 passed**.
- Frontend install/build: **NO VERIFICADO** en este entorno porque `corepack` no pudo acceder a `registry.npmjs.org`.
- Migraciones: archivos compilables y revisados estáticamente; **no se ejecutaron contra una instancia PostgreSQL real en este entorno**.

## Criterio de producción
Antes de liberar:
1. disponer de PostgreSQL/Redis reales;
2. ejecutar `alembic upgrade head` y comprobar `0039`/`0040` en la base objetivo;
3. ejecutar la suite con dependencias instaladas;
4. instalar frontend con `pnpm install --frozen-lockfile`;
5. ejecutar `pnpm run lint` y `pnpm run build`;
6. comprobar integración OIDC y tenant claims;
7. ejecutar pruebas de integración contra PostgreSQL con RLS habilitado.

No se considera que una fase esté probada en producción hasta completar esas comprobaciones sobre infraestructura real.
