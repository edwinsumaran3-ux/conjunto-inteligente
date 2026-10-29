# Runbook Operativo

## R1. ESP32 deja de reportar
1. Verificar `edge-gateway /devices`
2. Si `missed_heartbeats > 3`: enviar OTA reboot; si no responde, activar protocolo de sitio.
3. Revisar últimas 20 señales del dispositivo.

## R2. Cola saturada
1. Verificar `ingest_queue_size` en Prometheus.
2. Si > 70%: backpressure se activa automáticamente.
3. Si persiste > 5 min: escalar workers.
4. Si es por ataque: rate limit dinámico.

## R3. Base de datos caída
1. Verificar `pg_isready`.
2. Promover replica.
3. Eventos se acumulan en cola durable.
4. Al volver: workers drenan la cola.

## R4. IA no disponible
1. Verificar `ai_down_total`.
2. Sistema cambia a reglas locales.
3. Alertar al operador.
4. Si > 10 min: revisión humana.

## R5. Modo LOCAL
1. Edge sigue operando con reglas locales.
2. Dispositivos escriben a buffer local.
3. Al volver: sincronización y reconciliación.
4. Verificar `edge_local_buffer_size = 0`.

## R6. SOSPECHA DE SABOTAJE
1. TamperDetector emite `DEVICE_TAMPERING`.
2. Activar cámara de respaldo de zona.
3. Notificar a operador según protocolo autorizado.
4. Preservar logs write-once para forense.
