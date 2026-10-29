# Plan de pruebas de aceptación

1. Publicar evento válido → 200/OK → RabbitMQ → Worker → PostgreSQL → `/events`.
2. Publicar el mismo `event_id` 10 veces → una inserción durable y respuestas DUPLICATE posteriores.
3. Detener Ingestion → Edge conserva eventos en journal → restaurar → journal llega a cero.
4. Detener Worker → cola crece sin pérdida → restaurar → cola drena.
5. Detener PostgreSQL → Worker reintenta → no confirma mensajes hasta persistencia.
6. Enviar DOOR + MOTION → Correlation crea incidente de INTRUSION.
7. Enviar TAMPER → incidente CRITICAL → alerta.
8. IA sin modelos → endpoint informa unavailable; no se inventa una inferencia.
9. Invalidar firma → verificación rechaza el evento.
10. Reiniciar ESP32 → journal conserva eventos pendientes.
11. Cortar energía del nodo de datos y restaurar → ejecutar recuperación y verificar backup.
12. Ejecutar pruebas de carga sostenida y medir p95/p99, pérdida y profundidad de cola.
