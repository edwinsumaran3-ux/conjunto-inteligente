# Operación de producción: qué está realmente habilitado

## Habilitado en software

- Ingestión persistente y priorizada.
- Idempotencia de eventos.
- Backpressure.
- Correlación de incidentes.
- Agentes deterministas.
- Asesor neural opcional.
- Failover LLM.
- Circuit breaker.
- Protección de salida LLM.
- Permisos de proveedores.
- Aprobación humana.
- Registro durable de comandos.
- Nonce anti-replay.
- Ventana temporal de comandos.
- Firma HMAC por equipo.
- Fail-closed para adaptadores físicos no configurados.
- Métricas y health checks.

## No se considera habilitado automáticamente

Un dron, cámara PTZ, robot o actuador real no se considera operativo solo porque aparezca en el catálogo. Para pasar a producción física se deben instalar y probar el adaptador/SDK del fabricante, transporte, identidad del dispositivo, certificados/secretos, límites operacionales y procedimiento de aceptación.

La plataforma no falsifica telemetría ni simula una conexión de fabricante como si fuera real.

## Ruta de bajo coste

`ESP32/edge + reglas locales + RabbitMQ/PostgreSQL + Ollama` es la ruta recomendada para minimizar coste de APIs. Los proveedores externos permanecen deshabilitados hasta que exista una decisión explícita de habilitarlos.
