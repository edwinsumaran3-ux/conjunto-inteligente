# Bloque 7 — PowerBuilder Bridge (.NET 8)

Entrega de los archivos del Bloque 7 con la estructura solicitada.

## Rutas principales
- `legacy/powerbuilder-admin/bridge/` — bridge .NET 8.
- `legacy/powerbuilder-admin/sample-pb/scripts/` — objetos PowerBuilder de referencia.
- `legacy/powerbuilder-admin/pbl/` — contrato y guía.
- `legacy/powerbuilder-admin/tests/` — tests de mapper y contrato.
- `legacy/powerbuilder-admin/docker-compose.pb-bridge.fragment.yml` — fragmento para la compose raíz.

## Comandos
```bash
cd legacy/powerbuilder-admin/bridge
dotnet restore
dotnet build -c Debug

dotnet test ../tests/ConjuntoInteligente.PbBridge.Tests.csproj -c Debug

dotnet run --project . --urls http://localhost:5100
```

Swagger en Development: `http://localhost:5100/swagger`.

## Integración local

1. Aplica en el ERP la migración `0013_maintenance_operations` (`alembic upgrade head`) y arranca FastAPI en el puerto `8000`.
2. Arranca la API central .NET 8 en `5000`, con `CoreApi__BaseUrl=http://127.0.0.1:8000`.
3. Arranca el bridge en `5100`, con `Core__BaseUrl=http://127.0.0.1:5000` y un `PB__ServiceToken` secreto configurado fuera de `appsettings.json`.
4. PowerBuilder envía `X-PB-Service-Token` a todos los endpoints del bridge. Inicia sesión con `POST /pb/v1/auth/login`, entrega el JWT resultante como `Authorization: Bearer ...` en las solicitudes siguientes y no envía `X-Tenant-Id`.

El bridge solo reenvía el JWT de usuario al ERP; no configura un token de servicio ni decide el tenant. La API ERP valida JWT, roles y RLS. El usuario debe tener un perfil residente activo para crear solicitudes propias; listados y administración requieren rol gestor. La lista completa de estados, transiciones y límites está documentada en `00_ERP_Enterprise_v5/README_DEV.md`.

Rutas de escritura del bridge: `POST /pb/v1/orders`, `PATCH /pb/v1/orders/{id}`, `POST /pb/v1/orders/{id}/approve`, `PATCH /pb/v1/orders/{id}/status`, `POST/PUT /pb/v1/residents`, y `POST/PUT /pb/v1/vendors`. Los cambios de orden requieren `expected_version`; el ERP valida permisos, versiones, unidades, categorías y transiciones.

Los proyectos .NET y sus pruebas son independientes; las pruebas reemplazan el ERP por un servidor HTTP simulado. No hay compose raíz ni un `.pbl` compilable: los objetos PowerBuilder son exportaciones de referencia que se deben importar/compilar con PowerBuilder. El ERP no calcula saldos residenciales y no valida documentación de proveedores como archivos oficiales; esos campos no se presentan como verificados.
