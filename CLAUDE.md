# Conjunto Inteligente — memoria del proyecto para Claude Code

Plataforma de gestión de conjuntos residenciales (Colombia): seguridad, administración, servicios, compras, finanzas y comunidad. Idioma de la interfaz y de los textos: **español**.

## Mapa del repositorio
- `ConjuntoInteligente/` — **núcleo .NET** (`src/Api`, `src/Modules/{Identity,Tenants}`, `src/Persistence`, `tests/`). Solución: `ConjuntoInteligente.sln`.
- `apps/web-admin/frontend/web-admin/` — **frontend** React + Vite + TypeScript + Tailwind (`src/pages`, `src/components`, `src/lib`).
- `apps/mobile-residente/` — app móvil de residentes.
- `services/ai-agent/` — agentes de IA (Python). `services/powerbuilder-bridge/` — puente legado.
- `integrations/vigilancia-sistema/` — cámaras, zonas, incidentes, topología.
- `edge/` — firmware ESP32, gateway, C++. `00_ERP_Enterprise_v5/` — ERP Python (legado; contabilidad y finanzas).
- `contracts/openapi/conjunto-api.yaml` — contrato de la API. `docs/` — documentación y auditoría.

## Comandos (ejecútalos, no los supongas)
- Diagnóstico: `make doctor` · Instalar: `make install` · Stack local: `make dev` · Migraciones: `make migrate`, `NAME=... make migration-add`
- .NET: `dotnet build ConjuntoInteligente/ConjuntoInteligente.sln -warnaserror` · `dotnet test ConjuntoInteligente/ConjuntoInteligente.sln`
- Frontend (en `apps/web-admin/frontend/web-admin`): `pnpm install` · `pnpm dev` · `pnpm lint` (= `tsc --noEmit`) · `pnpm build`
- API tipada: `pnpm gen:api` tras cambiar `contracts/openapi/conjunto-api.yaml`.

## Reglas de trabajo (obligatorias)
1. **Nunca digas que algo funciona sin haberlo compilado y probado.** Cada cambio termina con build + pruebas en verde; muestra el resultado.
2. Trabaja en **cortes verticales** pequeños (entidad → migración → endpoint → pantalla → prueba). No escribas módulos enormes sin compilar.
3. `TreatWarningsAsErrors` está activo en .NET: corrige las advertencias, no las silencies.
4. **Aislamiento por conjunto (tenant)** en toda consulta y endpoint. Cada módulo nuevo lleva una prueba que demuestre que un tenant no ve datos de otro.
5. **Prohibido** datos de ejemplo en producción: los valores de demo solo con `import.meta.env.DEV`. Nada de `TODO` ni placeholders sin ticket en `docs/PLAN_CONSTRUCCION_100.md`.
6. Todo endpoint nuevo se agrega al contrato OpenAPI y al frontend se le regenera el tipo (`pnpm gen:api`).
7. Acciones con dinero, contratos o personas requieren **aprobación humana** registrada (quién, cuándo, qué).
8. Accesibilidad: controles con etiqueta, foco visible, contraste, teclado. Todos los textos en español.
9. Al terminar un corte, actualiza el estado en `docs/PLAN_CONSTRUCCION_100.md` y `docs/AUDITORIA_VERIFICACION.md` con lo que realmente se ejecutó.
10. Si algo no se puede probar (sin red, credenciales, hardware), dilo y deja el paso exacto para probarlo.

## Estado y plan
La fuente de verdad de qué falta está en `docs/PLAN_CONSTRUCCION_100.md`. Empieza siempre por la **Fase 0**.
