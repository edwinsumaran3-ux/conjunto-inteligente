# Plataforma Neural de Ingeniería

Esta capa integra redes neuronales como **asesores controlados**, no como autoridades de ejecución.

## Costo mínimo
- **Opción 0 USD de API:** Ollama en infraestructura propia; el costo real es hardware/electricidad.
- Proveedores externos son opcionales y se habilitan por permiso explícito y variable de entorno.
- El sistema puede operar sin ningún proveedor externo: `status=degraded` y conserva el flujo determinista.

## Proveedores
- `ollama`: inferencia local.
- `openai`: Responses API.
- `gemini`: Gemini API.
- `anthropic`: Messages API.
- `openai_compatible`: cualquier endpoint compatible administrado por el operador.

## Permisos
`AI_PROVIDER_PERMISSIONS` define por proveedor los propósitos permitidos (`advisory`, `event_analysis`, `vision_summary`, `engineering`) y el máximo de tokens.

## Regla de seguridad
La red neuronal nunca recibe herramientas de dron, robot, acceso, actuador o sensor. Puede producir análisis, hipótesis y recomendaciones. La decisión operativa sigue en agentes deterministas + políticas + aprobación humana.

## Drones y sensores
Los eventos ESP32, sensores láser/IR, cámaras, telemetría de drones y descubrimiento de equipos pueden alimentar el contexto del gateway. No se permite que el modelo transforme esa evidencia en un comando físico directo.

## Integración futura
El gateway es una frontera estable para conectar el orquestador de agentes y el centro de incidentes sin acoplarlos a un proveedor específico.


## Auditoría
Cada inferencia debe conservar un identificador, tenant, propósito, proveedor/modelo, estado y huella del prompt. No se guarda el prompt completo por defecto y nunca se deben persistir claves o secretos.
