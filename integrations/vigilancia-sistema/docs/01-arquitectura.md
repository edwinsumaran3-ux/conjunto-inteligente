# Arquitectura endurecida

```text
ESP32 --MQTT QoS1--> Edge Gateway --HTTP--> Ingestion --RabbitMQ quorum--> Worker --PostgreSQL--> Dashboard
                                      |                                      |
                                      +-- persistent local journal           +--> events.fanout --> Correlation
                                                                                         |
                                                                                         +--> incidents.fanout --> Incident Core --> alerts.fanout --> Notifications
```

La cola es durable y los mensajes son persistentes. PostgreSQL es la fuente de verdad de eventos e incidentes. Redis solo acelera correlación/idempotencia y no es la autoridad final.
