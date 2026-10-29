# Contrato pb-v1 (congelado)

Todos los endpoints devuelven `PbResponse<T>` con `ok`, `code`, `message`, `data`, `errors`, `traceId` y `ts`.

## Endpoints
- GET `/pb/v1/tenants/current`
- GET `/pb/v1/tenants`
- POST `/pb/v1/orders/list`
- GET `/pb/v1/orders/{id}`
- GET `/pb/v1/residents/list`
- GET `/pb/v1/residents/{id}`
- GET `/pb/v1/vendors/list`
- GET `/pb/v1/catalogos/estados-orden`
- GET `/pb/v1/catalogos/categorias`
- GET `/pb/v1/catalogos/severidades`
- GET `/health`
- GET `/ready`

## Reglas
1. No renombrar campos existentes.
2. No eliminar campos existentes.
3. Agregar campos nuevos solo al final y opcionales.
4. No cambiar tipos de dato.
5. Cualquier cambio incompatible exige v2.
