# Conjunto Inteligente

Plataforma SaaS multi-tenant para conjuntos residenciales, edificios y condominios. Este workspace integra el ERP existente con componentes de vigilancia, edge IoT, IA y un puente legado; no constituye una solución monolítica lista para producción.

## Componentes presentes

| Componente | Ruta | Estado comprobado |
|---|---|---|
| ERP API Python/FastAPI y PostgreSQL | `00_ERP_Enterprise_v5/backend/` | API modular con suite unitaria/contratos y suite E2E/integración configurada en CI con PostgreSQL 16 descartable. La ejecución del job queda pendiente de observar en GitHub Actions. |
| Frontend React/Vite del ERP | `00_ERP_Enterprise_v5/frontend/` | Panel operativo conectado con FastAPI; lint, TypeScript, pruebas y build se ejecutan en CI. |
| Agente/orquestador de IA | `services/ai-agent/conjunto-ai-block2/` | 24 pruebas aprobadas en su entorno virtual; no se validó entrenamiento real con PyTorch. |
| Vigilancia e integraciones IoT | `integrations/vigilancia-sistema/` | Plataforma Python y pruebas presentes; verificación de vigilancia aprobó 42 pruebas y HIL del gateway 2. |
| Gateway C++20 | `edge/gateway/conjunto/edge/` | Compilación Linux en contenedor y suite CTest: 21 aprobadas. |
| Firmware ESP32 | `edge/esp32-firmware/edge/esp32/firmware/` | Pruebas nativas PlatformIO configuradas en CI; hardware físico y release firmado requieren validación/provisión externa. |
| API central .NET 8 | `services/core-api-dotnet/` | Gateway HTTP con paso de JWT, health/readiness, OpenAPI del ERP y pruebas automatizadas configuradas en CI. PostgreSQL/RLS permanecen en FastAPI. |
| API ERP de mantenimiento | `00_ERP_Enterprise_v5/backend/app/modules/maintenance/` | Órdenes con aprobación, transiciones auditadas, proveedores y asignación de residentes a unidades; migración 0013 pendiente de aplicar en despliegues existentes. |
| Puente PowerBuilder/.NET 8 | `services/powerbuilder-bridge/ConjuntoInteligente-Bloque7-PowerBuilder-Bridge/legacy/powerbuilder-admin/` | Conectado a API central con login ERP/JWT de usuario y contratos de mantenimiento, residentes, proveedores y tenant actual; build y pruebas .NET configurados en CI. Incluye exportaciones de objetos PowerBuilder, no un `.pbl` compilable. |

## Brechas conocidas del workspace integrado

- No están presentes `apps/web-admin/`, `apps/mobile-residente/`, una especificación OpenAPI raíz ni una compose monolítica. El frontend presente pertenece al ERP.
- No hay un artefacto `.pbl` ni herramienta PowerBuilder para compilar las muestras exportadas.
- El saldo residencial no existe en el ERP y se devuelve nulo; la vigencia documental del proveedor depende de una fecha declarada, no de validar archivos oficiales. La integración usa JWT de usuario y requiere la migración 0013.
- La vista web diferencia anomalías, propuestas BIM y órdenes operativas; las acciones de aprobación/estado solo se habilitan para gestores y se vuelven a validar en el ERP. Para solicitudes propias se usa `/api/v1/maintenance/orders/mine`.
- Los servicios tienen composiciones y guías independientes; no se debe asumir que `docker compose` desde esta raíz levanta el sistema completo.
- La validación no certifica despliegue productivo, hardware físico ni integración con proveedores externos.
- Los nuevos jobs de PostgreSQL, API .NET, bridge y firmware en `.github/workflows/ci.yml` deben ejecutarse y revisarse en GitHub Actions; el archivo local por sí solo no certifica un pipeline exitoso.
- La compilación release del firmware exige clave de firma y falla de forma explícita cuando falta; CI ejecuta las pruebas nativas sin usar secretos ni afirmar que el hardware fue probado.

## Desarrollo

El `Makefile` contiene accesos directos para los módulos presentes. Para una pila local completa, usa la documentación específica de cada módulo y configura sus dependencias y secretos por separado. Ejemplos:

```bash
make test-edge
make test-dotnet
make test-web
```

Para validar PostgreSQL, consulta `00_ERP_Enterprise_v5/` y ejecuta sus pruebas de integración contra una base desechable debidamente provisionada. La API central se configura con `CoreApi__BaseUrl` y puede ejecutarse desde `services/core-api-dotnet/`; sus instrucciones de desarrollo y contenedor están en su [README](services/core-api-dotnet/README.md).
