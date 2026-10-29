# Fusión Vigilancia + Conjunto Inteligente — Fase 5

## Estado
Fusión realizada sobre el proyecto Conjunto Inteligente Fase 5 existente.

## Preservación
- No se eliminaron archivos fuente del proyecto base.
- Se conservaron todos los archivos fuente del ZIP base; se retiraron únicamente artefactos generados `__pycache__`/`.pytest_cache`.
- Se convirtió `00_ERP_Enterprise_v5/test_write` de archivo vacío a marcador explícito de compatibilidad.
- Se eliminó el gateway neural duplicado que venía dentro de Vigilancia porque el proyecto base ya posee `services/ai-agent/conjunto-ai-block2` como plano LLM compartido.

## Integración
- Vigilancia queda bajo `integrations/vigilancia-sistema`.
- ESP32, sensores, cámaras, drones, malla, ingestion, correlación, incident-core y EquipmentRegistry se conservan.
- El agente de Vigilancia consulta `CONJUNTO_AI_URL/analyze/surveillance_advisor` para obtener asesoría neural.
- La asesoría se registra como evidencia; no tiene permisos de ejecución física.
- El LLM de Conjunto incorpora `deterministic`, `ollama`, `openai`, `gemini`, `anthropic` y `openai_compatible`.
- `AI__LLM_ALLOWED_PROVIDERS` funciona como lista explícita de permisos y `AI__LLM_PROVIDER` define el orden.
- Ollama permite inferencia local sin coste de API; requiere hardware/energía locales.

## Seguridad física
- `EquipmentRegistry` rechaza firmas placeholder/no verificadas.
- Los adaptadores físicos continúan fail-closed.
- Drones no reciben navegación autónoma desde el LLM.
- Sensores de detección permanecen en edge.
- Las acciones de impacto requieren las políticas y aprobación correspondientes.

## Validación ejecutada
- AI service: 18 tests PASS.
- Vigilancia agent-orchestrator: 2 tests PASS.
- Vigilancia contracts/security: 4 tests PASS.
- Compilación Python del monorepo: 550 archivos, 0 errores.
- YAML de ambos docker-compose: parseado correctamente.
- Preservación del ZIP base: 1074 archivos fuente presentes, 0 faltantes.

## Validaciones no ejecutadas
- `dotnet build`: el entorno de validación no dispone de .NET SDK.
- Build TypeScript del web-admin: no hay `pnpm`/`node_modules`; `npm ci` no puede usar el proyecto porque este frontend conserva `pnpm-lock.yaml` y no tiene `package-lock.json`.
- Arranque E2E con Docker: Docker no está disponible en este entorno.
- Llamadas reales a proveedores externos: no se ejecutaron para no inventar credenciales ni generar consumo.

Estas limitaciones no se marcan como PASS.
