# Matriz FMEA — Análisis de Modos de Falla

| Componente | Falla | Detección | Recuperación | Operación degradada |
|---|---|---|---|---|
| ESP32 | bloqueo | hardware watchdog | reboot automático | sensores locales |
| ESP32 | sin red | MQTT disconnect | reconexión + failover edge | buffer local |
| Sensor | desconectado | diagnóstico periódico | marcar fallo | otras capas |
| Cámara | sin video | frame monitor | reconnect + restart stream | otras cámaras |
| Cámara | storage lleno | storage monitor | rotación / purga | grabación a menor calidad |
| MQTT broker | caída | health check | reconexión cliente | buffer local |
| Edge Gateway | caída | heartbeat | failover a edge-02 | zona B sigue |
| Ingestion | caída | healthz | LB + réplica | edge → otro ingestion |
| Queue (RabbitMQ) | saturación | métricas | backpressure | descartar TELEMETRY |
| Queue | nodo caído | quorum | failover automático | quórum 2/3 |
| DB | caída | health check | replica promote | cola durable |
| DB | disco lleno | métricas | purga + escalado | retention reducida |
| IA | timeout | timeout 2s | modelo alternativo | reglas locales |
| IA | incierta | conf < umbral | escalar a humano | cola de revisión |
| Notificaciones | fallo | retry | reintentos exponenciales | fallback canal |
| Internet | caída | ping | reconexión | modo LOCAL |
| Firmware | update fallido | health check post-OTA | rollback | versión anterior |
| Energía | pérdida | UPS telemetría | respaldo batería | modo seguro |
| Redis | caída | health check | replica promote | sin cache |
| Supervisor | caída | auto-heartbeat | supervisor secundario | alerta |
