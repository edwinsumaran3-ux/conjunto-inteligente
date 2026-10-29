# API central .NET 8

Gateway HTTP para centralizar el acceso de clientes a la API ERP FastAPI existente.
No mantiene un segundo modelo de datos: PostgreSQL, JWT, permisos, tenant y RLS
siguen siendo responsabilidad exclusiva del ERP.

## Ejecución local

Con el ERP iniciado en `http://127.0.0.1:8000`:

```powershell
dotnet test tests\ConjuntoInteligente.CoreApi.Tests\ConjuntoInteligente.CoreApi.Tests.csproj
dotnet run --project src\ConjuntoInteligente.CoreApi\ConjuntoInteligente.CoreApi.csproj --urls http://localhost:5000
```

Configura `CoreApi__BaseUrl` para cambiar el origen de FastAPI. La API central
publica `/healthz`, `/readyz`, `/docs`, `/openapi.json` y reenvía `/api/v1/*`.
El readiness comprueba el `/readyz` del ERP; `/healthz` solo comprueba que el
proceso .NET esté vivo.

Las solicitudes autenticadas deben enviar el JWT de usuario en la cabecera HTTP
`Authorization`. La API transmite ese JWT al ERP y no confía en `X-Tenant-Id` ni
en el token privado del bridge PowerBuilder para seleccionar el tenant. Los
timeouts se configuran con `CoreApi__RequestTimeoutSeconds` y
`CoreApi__ReadinessTimeoutSeconds`.

## Contenedor

Desde esta carpeta:

```powershell
docker build -t conjunto-core-api .
docker run --rm -p 5000:8080 `
  -e CoreApi__BaseUrl=http://host.docker.internal:8000 `
  conjunto-core-api
```

En un despliegue Compose, configura `CoreApi__BaseUrl` con el nombre DNS del
servicio ERP de esa red. No se incluye una compose raíz porque el workspace aún
no tiene una topología monolítica.

## Contrato y límites actuales

`/openapi.json` y `/docs` se sirven desde el ERP para que el contrato publicado
refleje las rutas realmente implementadas. El bridge PowerBuilder puede
configurarse para usar este origen y consume `/api/v1/maintenance/*` y
`/api/v1/tenants/current` mediante el gateway. El bridge exige su token de
cliente (`X-PB-Service-Token`) y el JWT de usuario emitido por `/pb/v1/auth/login`;
solo este JWT llega al ERP para decidir usuario, roles y tenant. El gateway no
acepta `X-Tenant-Id` como autoridad.

Antes de usar la fase de mantenimiento, aplica `alembic upgrade head` en el ERP.
La disponibilidad y reglas de estados, roles, aprobación, residentes, unidades y
proveedores se documentan en `00_ERP_Enterprise_v5/README_DEV.md`. Residentes,
proveedores, códigos de tenant y saldos no se inventan: datos que el ERP no
mantiene se devuelven nulos o quedan explícitamente fuera del contrato.
