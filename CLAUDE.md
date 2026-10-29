# Conjunto Inteligente — memoria del proyecto para Claude Code

Plataforma de gestión de conjuntos residenciales (Colombia): seguridad, administración, servicios, compras, finanzas y comunidad. Idioma de la interfaz y de los textos: **español**.

## Mapa del repositorio
- `00_ERP_Enterprise_v5/backend/` — ERP API Python/FastAPI, PostgreSQL, RLS y módulos funcionales.
- `00_ERP_Enterprise_v5/frontend/` — frontend React/Vite del ERP.
- `frontend/` — referencia visual estática del centro de mando; no asumir que es la aplicación operativa conectada.
- `services/core-api-dotnet/` — API central .NET 8. `services/powerbuilder-bridge/` — puente legado.
- `services/ai-agent/conjunto-ai-block2/` — agente/orquestador Python.
- `integrations/vigilancia-sistema/` — cámaras, zonas, incidentes e integración de vigilancia.
- `edge/gateway/conjunto/edge/` — gateway C++20; `edge/esp32-firmware/edge/esp32/firmware/` — firmware ESP-IDF.
- `README.md`, `docs/` y las guías de cada componente son la referencia del workspace actual. No asumir apps, contratos OpenAPI ni soluciones que no estén en el árbol.

## Comandos (ejecútalos, no los supongas)
- Diagnóstico: `make doctor` · Instalar: `make install` · Stack local: `make dev` · Migraciones: `make migrate`, `NAME=... make migration-add`
- Gateway: `make test-edge`.
- API/bridge .NET: `make test-dotnet`.
- Frontend del ERP: `make test-web`; consulta `00_ERP_Enterprise_v5/frontend/`.
- Firmware: `make build-esp32` y la guía de `edge/esp32-firmware/edge/esp32/firmware/README.md`; la compilación no equivale a prueba física.
- Ejecuta los comandos definidos en `Makefile` y la guía del componente; no ejecutes instalaciones ni migraciones sin revisar el gestor y el entorno.

## Reglas de trabajo (obligatorias)
1. **Nunca digas que algo funciona sin haberlo compilado y probado.** Cada cambio termina con build + pruebas en verde; muestra el resultado.
2. Trabaja en **cortes verticales** pequeños (entidad → migración → endpoint → pantalla → prueba). No escribas módulos enormes sin compilar.
3. `TreatWarningsAsErrors` está activo en .NET: corrige las advertencias, no las silencies.
4. **Aislamiento por conjunto (tenant)** en toda consulta y endpoint. Cada módulo nuevo lleva una prueba que demuestre que un tenant no ve datos de otro.
5. **Prohibido** datos de ejemplo presentados como reales. Identifica simulaciones, placeholders y funcionalidades que no se han probado; registra brechas en `docs/PROJECT_REQUIREMENTS_TRACEABILITY.md`.
6. Antes de añadir endpoints o integraciones, localiza el router/contrato real del componente; no generes tipos desde un OpenAPI raíz que no existe.
7. Acciones con dinero, contratos o personas requieren **aprobación humana** registrada (quién, cuándo, qué).
8. Accesibilidad: controles con etiqueta, foco visible, contraste, teclado. Todos los textos en español.
9. Al terminar un corte, actualiza la guía del componente y, si cambia el alcance integrado, `docs/PROJECT_REQUIREMENTS_TRACEABILITY.md` con lo realmente ejecutado.
10. Si algo no se puede probar (sin red, credenciales, hardware), dilo y deja el paso exacto para probarlo.

## Estado y plan
La brecha integrada y los requisitos de hardware se registran en `docs/PROJECT_REQUIREMENTS_TRACEABILITY.md` y `docs/HARDWARE_REFERENCE_ARCHITECTURE.md`. Empieza comprobando el estado real de los componentes antes de asumir fases o despliegues.
