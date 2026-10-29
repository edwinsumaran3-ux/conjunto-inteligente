# Revisión v2 · Conjunto Inteligente

## Correcciones
- Makefile: DOTNET_SOLUTION, COMPOSE_*, WEB_DIR, MOBILE_DIR y AI_DIR apuntaban a rutas inexistentes; ahora apuntan a las reales. AI_DIR usa `app` (no `orchestrator`).
- web-admin: `theme('colors.bg-card')` era inválido en Tailwind (rompía el CSS de MapLibre) → `colors.bg.card`.
- web-admin: `gen:api` apuntaba a `contracts/openapi` (no existe). Ahora usa `OPENAPI_SPEC` o `./openapi/conjunto-api.yaml`.
- web-admin: el modo mock ya NO puede activarse en build de producción (antes `VITE_USE_MOCK=true` dejaba entrar con cualquier contraseña de 3+ caracteres).
- web-admin: `VITE_DEFAULT_TENANT_ID` se declaraba y no se usaba; ahora es fallback del header X-Tenant-Id.
- Dashboard: el KPI de Seguridad mostraba 48 con la leyenda "12 cámaras activas" (invertido).
- Mapa: `orderId` se inserta en HTML del popup sin escapar → `encodeURIComponent`.
- Mock: placa JKT-882 → JKT-482 (coherente con el diseño).

## Diseño 3D
- `index.css`: paneles en relieve, teclas `.btn-*` que se hunden al presionar, `.chip` de filtros, inputs hundidos, respeta `prefers-reduced-motion`.
- Layout, Orders y KpiCard migrados a las nuevas teclas.
- `docs/prototipo-centro-de-mando.html`: centro de mando de referencia (mapa isométrico, alertas en vivo, WhatsApp, cadena de suministro).

## Pendiente (no verificado aquí)
- No pude ejecutar `pnpm build`, `dotnet build` ni `pytest` (sin red ni toolchains). Los 464 archivos Python sí compilan (`compileall`).
- Falta el contrato OpenAPI real del backend .NET.
- docker-compose override/prod solo existen para `edge/conjunto-cxx`, no para ConjuntoInteligente.
- Las páginas Compras, Finanzas, Residentes, Seguridad, Parqueaderos y Documentos del web-admin siguen deshabilitadas ("Próximamente").

## Actualización (auditoría contra el prompt maestro)
Ver `docs/AUDITORIA_VERIFICACION.md`, `docs/` (16 documentos), `docs/diagrams/` (26 diagramas), `.github/workflows/ci.yml` y `ConjuntoInteligente/Dockerfile.api`.

## Fase 2 — 2026-10-03

Se añadió la capa operativa de Fase 2 sobre el trabajo existente, preservando FloorPlan3D PRO y las rutas anteriores. Nuevas vistas: planos/asignación, proceso/cadena de suministro, reportes y presentación comercial. El dashboard fue ampliado con mapa visual, cámaras, detalle de servicio, proceso, reportes y experiencia residente. También se amplió la navegación con Zonas Comunes, Reportes e Informes, Configuración e IA Asistente.
