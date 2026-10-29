# Checklist de producción

## Antes del despliegue
- [ ] Generar secretos aleatorios para PostgreSQL, Redis y RabbitMQ; nunca usar valores del `.env.example`.
- [ ] Provisionar PKI mediante un gestor de secretos. El script incluido sirve para un entorno controlado; para producción empresarial usar CA/PKI administrada.
- [ ] Cambiar Mosquitto a TLS y deshabilitar el listener 1883.
- [ ] Provisionar CA en cada ESP32 y eliminar `setInsecure` (el firmware endurecido ya rechaza la ausencia de `/mqtt_ca.pem`).
- [ ] Firmar firmware y validar la firma antes de OTA.
- [ ] Habilitar NTP/RTC seguro y verificar sincronización antes de aceptar eventos.
- [ ] Configurar un proveedor real de notificaciones (webhook, correo, SMS o push) y probar reintentos.
- [ ] Configurar almacenamiento de vídeo externo/retención; no guardar streams dentro del contenedor.
- [ ] Añadir autenticación/autorización delante del dashboard y API.
- [ ] Terminar TLS para API/dashboard mediante reverse proxy/ingress.
- [ ] Activar backups de PostgreSQL y probar restauración.
- [ ] Ejecutar pruebas de carga y caos con datos sintéticos antes de conectar sensores reales.

## Garantías implementadas
- Evento original conservado durante modo degradado.
- ACK de dispositivo separado del procesamiento posterior.
- Idempotencia en Redis + restricción durable en PostgreSQL.
- Cola RabbitMQ quorum y mensajes persistentes.
- Correlación e incidentes conectados realmente por exchanges AMQP.
- Dashboard consume datos reales, sin cámaras/dispositivos ficticios.

## Límites honestos
Ningún software puede garantizar que jamás fallará. Esta versión elimina errores conocidos del paquete entregado y agrega controles para recuperación, pero la disponibilidad final depende también de hardware, red, energía, almacenamiento, configuración de PKI y operación.
