# Guía de integración PowerBuilder 2022 R3 ↔ Conjunto Inteligente

## Requisitos
- PowerBuilder 2022 R3 con target .NET.
- Acceso de red al bridge en `http://<host>:5100`.
- Token de servicio en `X-PB-Service-Token`.

## Pasos
1. Importar los `.sru`, `.srw` y `.srd` de `sample-pb/scripts/`.
2. Configurar URL y token mediante `nvo_api_client.of_set_config`.
3. Abrir `w_orders` y ejecutar Actualizar.
4. Extender con nuevas ventanas/DataWindows manteniendo `pb-v1`.

## Envelope
`ok`, `code`, `message`, `data`, `errors`, `traceId`, `ts`.

## Errores estables
`PB_AUTH_REQUIRED`, `PB_FORBIDDEN`, `PB_NOT_FOUND`, `PB_VALIDATION`, `PB_CORE_UNAVAILABLE`, `PB_CORE_TIMEOUT`, `PB_CORE_ERROR`, `PB_INTERNAL`, `PB_RATE_LIMITED`.

El bridge no implementa reglas de negocio ni guarda estado persistente. Los cambios incompatibles requieren `pb-v2`.
