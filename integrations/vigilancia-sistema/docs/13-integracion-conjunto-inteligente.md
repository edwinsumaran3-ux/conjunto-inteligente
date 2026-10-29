# Integración con Conjunto Inteligente — Fase 5

## Arquitectura integrada

```text
ESP32 / sensores / cámaras / drones
             │
             ▼
   vigilancia-sistema (edge)
             │
       incidentes/eventos
             │
             ├──────────────► Centro de Incidentes
             │
             └──────────────► Conjunto AI Orchestrator
                                   │
                     deterministic / Ollama / OpenAI / Gemini / Anthropic
                                   │
                           advisory + uncertainty
                                   │
                    políticas + aprobación humana
                                   │
                         acciones operativas
```

El LLM compartido pertenece a `services/ai-agent/conjunto-ai-block2`; no se mantiene un segundo gateway LLM dentro de Vigilancia. Esto evita duplicar circuitos, credenciales, políticas y auditoría.

## Drones
El catálogo y las fronteras de adaptadores de drones se conservan en Vigilancia. La IA puede analizar telemetría y eventos, pero no recibe permisos para vuelo, navegación, seguimiento de personas ni acciones físicas autónomas.

## Sensores
ESP32, barreras láser/IR de detección, tamper, puertas y movimiento continúan en el edge. Los eventos se conservan con idempotencia y journal local.

## Permisos de redes neuronales
`AI__LLM_ALLOWED_PROVIDERS` es una lista explícita de proveedores permitidos. `AI__LLM_PROVIDER` define el orden. La ausencia de una credencial no habilita un proveedor remoto. `deterministic` y `ollama` permiten operación sin gasto de API; Ollama requiere recursos locales.

## Regla de seguridad
El LLM no ejecuta herramientas físicas. Todas las acciones pasan por políticas deterministas, autorización del operador y las fronteras `EquipmentRegistry`/adaptadores fail-closed.
