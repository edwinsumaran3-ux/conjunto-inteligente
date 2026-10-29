# Conjunto Inteligente — Auditoría de integración v8

Fecha de revisión: 2026-10-11  
Alcance: auditoría estática de integración sobre el árbol `ConjuntoInteligente_COMPLETO_FUSIONADO_BIM_GEMELO/b09work` del paquete v7. No se modificó código de negocio existente; se añadieron este informe y `tools/validate_integration_v8.py`.

## Resultado ejecutivo

**La integración completa todavía no está demostrada.** Las suites Python ejecutadas pasan, pero la auditoría estática encontró errores de configuración que bloquean el arranque reproducible del ERP y del stack `edge/conjunto-cxx`. El frontend no se pudo compilar porque no hay `node_modules` ni caché local de npm en este entorno. No se pudo ejecutar Docker/Compose.

## Pruebas ejecutadas en esta revisión

| Componente | Comando | Resultado |
|---|---|---:|
| ERP | `python -m pytest -q` en `00_ERP_Enterprise_v5` | 146 passed |
| Vigilancia | `python -m pytest -q tests` en `integrations/vigilancia-sistema` | 42 passed |
| Agente IA | `python -m pytest -q` en `services/ai-agent/conjunto-ai-block2` | 24 passed |
| Orquestador | `python -m pytest -q` en `integrations/vigilancia-sistema/services/agent-orchestrator` | 4 passed |
| Lint frontend | `node scripts/lint.mjs` en `00_ERP_Enterprise_v5/frontend` | PASS |
| Imports locales frontend | `python tools/validate_integration_v8.py` | 9 imports revisados, sin rutas faltantes |
| ZIP v7 original | `zipfile.testzip()` | Sin miembros dañados detectados |

Total de suites Python: **216 pruebas aprobadas**. Estas pruebas no equivalen a 216 flujos end-to-end del sistema completo.

## Bloqueos encontrados

1. **ERP Dockerfile ausente:** `00_ERP_Enterprise_v5/docker-compose.dev.yml` y `docker-compose.test.yml` usan `build: .`, pero no existe `00_ERP_Enterprise_v5/Dockerfile`. La validación de esos stacks falla antes de construir contenedores.
2. **Backend ERP incompleto para arranque:** el árbol revisado solo contiene un subconjunto de `backend/app`; no se encontró un `main.py`/entrypoint ASGI en la raíz ERP y no existe Dockerfile raíz. No se debe crear un contenedor ficticio para esconderlo: hay que reconstruir o localizar el entrypoint real y sus dependencias.
3. **Stack C++/edge con rutas de build ausentes:** `edge/conjunto-cxx/docker-compose.yml` referencia contextos como `edge`, `ai`, `legacy/powerbuilder-admin/bridge` y `frontend/web-admin` que no existen en ese árbol; además, el Dockerfile de API referenciado no está presente en la ruta configurada.
4. **Frontend sin dependencias instaladas:** no existe `frontend/node_modules` y la caché local de npm está vacía. Por eso no se ejecutaron `typecheck`, Vitest ni `vite build`; el lint de Node sí pasó.
5. **Árboles paralelos:** el paquete contiene varias copias/versiones de `b09work` (árbol BIM fusionado, árbol consolidado y versiones de recuperación). No se unificaron automáticamente porque hacerlo sin un diff semántico y pruebas de regresión podría sobrescribir código distinto.
6. **Integración física/tiempo real no demostrada:** no se ejecutó una prueba real de ESP32/sensor → gateway → API → persistencia/Outbox → worker/agente → actualización de frontend.
7. **Infraestructura real no ejecutada:** no se pudo levantar Docker, PostgreSQL, Redis, RabbitMQ, aplicar migraciones ni validar aislamiento multi-tenant en una instancia viva.

## Hallazgos estáticos reproducibles

El script `tools/validate_integration_v8.py` comprueba los scripts del frontend, imports locales, dependencias instaladas y contextos/Dockerfiles de los cuatro Compose principales. Resultado de esta ejecución: **8 PASS, 4 FAIL, 1 BLOCKED**. Los fallos son los contextos/Dockerfiles descritos arriba; el bloqueo es la ausencia de dependencias frontend.

Ejecutar desde `ConjuntoInteligente_COMPLETO_FUSIONADO_BIM_GEMELO/b09work`:

```bash
python tools/validate_integration_v8.py
```

El script sale con código distinto de cero si encuentra fallos estáticos.

## Plan técnico siguiente (sin borrar ni sustituir código existente)

1. Comparar semánticamente las copias paralelas y elegir un árbol canónico con manifiesto de archivos conservados.
2. Recuperar/localizar el entrypoint real del ERP y crear un Dockerfile solo cuando el módulo de arranque y la configuración estén confirmados.
3. Reparar las rutas de build de Compose contra archivos existentes; no crear carpetas vacías ni Dockerfiles de relleno.
4. Instalar dependencias frontend desde un lockfile reproducible, ejecutar typecheck, pruebas y build.
5. Levantar servicios con Docker en un entorno compatible; ejecutar migraciones, health checks y pruebas de aislamiento/seguridad.
6. Crear una prueba end-to-end con evento simulado y después validación de hardware real.
7. Generar nuevo ZIP solo después de registrar comandos, resultados y limitaciones.

## Integridad y preservación

No se borraron ni modificaron archivos de aplicación heredados en esta revisión. Se añadieron el validador estático y este informe al árbol BIM fusionado del paquete v7. La integridad del ZIP no prueba que todos los bytes del archivo fuente original dañado hayan sido recuperados; esa incertidumbre permanece.
