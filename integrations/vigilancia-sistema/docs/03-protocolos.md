# Protocolos y garantías

- MQTT entre dispositivo y Edge: QoS 1; el evento permanece en el buffer hasta ACK `OK` o `DUPLICATE`.
- HTTP Edge→Ingestion: timeout corto; ante fallo el evento se conserva en el journal local.
- RabbitMQ: cola quorum durable y mensajes persistentes.
- PostgreSQL: `event_id` PRIMARY KEY y `(device_id, sequence_number)` UNIQUE.
- Correlación: Redis con ventana temporal; incidentes persistidos en PostgreSQL.
- Seguridad: producción debe usar TLS/mTLS, secretos externos y firma de eventos/firmware con claves protegidas.
