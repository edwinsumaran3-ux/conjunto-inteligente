# Producción — plano de ingeniería de campo

La plataforma fusiona Conjunto Inteligente y Vigilancia como un sistema distribuido con un único plano LLM.

## Principios

1. El edge continúa operando con reglas locales si el centro o el LLM están fuera de servicio.
2. Los eventos son idempotentes y persistentes antes de considerarse aceptados por los consumidores.
3. Las decisiones de IA son asesoramiento; las acciones físicas pasan por política, autorización y adaptador.
4. Todo comando físico tiene nonce, ventana temporal, firma HMAC por equipo y journal persistente.
5. El modelo local (Ollama) es la ruta de coste mínimo. Los proveedores externos son opt-in por configuración.
6. No se almacenan secretos en prompts, logs ni eventos.
7. La telemetría se trata como dato no confiable hasta validación de identidad, secuencia y frescura.

## Capas

Edge ESP32/cámara/dron → MQTT/RabbitMQ → Ingestion → Correlation → Incident Core → Agent Orchestrator → AI Orchestrator → Response Guard → Human Approval → Equipment Registry → Adapter → equipo.

## Continuidad

- pérdida de LLM: reglas deterministas continúan;
- pérdida de WAN: edge buffer y reintento;
- pérdida de RabbitMQ: no se confirma ingestión;
- duplicados: idempotencia por event_id/command nonce;
- comandos expirados: rechazo;
- firma inválida: rechazo;
- adaptador no conectado: fail-closed;
- aprobación vencida: rechazo;
- proveedor LLM agotado: circuit breaker + fallback.

## Coste

El stack puede operar con `deterministic + Ollama` sin APIs externas. Las integraciones OpenAI/Gemini/Anthropic/OpenAI-compatible permanecen disponibles mediante permisos explícitos y variables de entorno.

## No demo

Los adaptadores de fabricantes siguen deliberadamente en frontera `fail-closed` hasta que se configure el SDK/protocolo real del fabricante, credenciales, endpoint y procedimiento de aceptación. Un adaptador simulado no se presenta como control físico de producción.
