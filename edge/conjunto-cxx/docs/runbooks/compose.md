# Operación del stack Docker

## Levantar

```bash
# Primera vez
cp .env.example .env
./scripts/compose-up.sh

# Solo core (api, ai, web, pb-bridge, infra data)
./scripts/compose-up.sh core

# Solo edge (mosquitto, edge gateway)
./scripts/compose-up.sh edge

# Herramientas opcionales (adminer, mailhog)
docker compose --profile tools up -d
```

Detener

```bash
docker compose down               # para todo, preserva volúmenes
docker compose down -v            # para todo y borra volúmenes (¡peligro!)
docker compose stop api ai        # detiene solo algunos
```

Ver estado

```bash
docker compose ps
docker compose ps --format json | jq
```

Logs

```bash
docker compose logs -f api
docker compose logs -f --tail=100 api ai edge
docker compose logs --since 5m
```

Reconstruir un servicio tras cambiar el código

```bash
docker compose build api
docker compose up -d api
```

Ejecutar un comando puntual

```bash
docker compose exec postgres psql -U ci -d conjunt_inteligente
docker compose exec rabbitmq rabbitmqctl list_queues
docker compose exec redis redis-cli -a $REDIS_PASSWORD
docker compose exec mosquitto mosquitto_sub -t 'conjunto/+/events' -v
```

Migraciones EF Core

```bash
docker compose exec api dotnet ef database update \
  --project /src/Services/Tenants/... --startup-project /src/Api/ConjuntoInteligente.Api
```

Dashboards

· Grafana: http://localhost:3000 (admin / GRAFANA_ADMIN_PASSWORD)
  · Dashboard "Conjunto Inteligente · Overview" preinstalado.
  · Datasources: Prometheus, Loki, Tempo.
· Prometheus: http://localhost:9090
· RabbitMQ Management: http://localhost:15672
· MinIO Console: http://localhost:9001

Verificar trazas end-to-end

1. Hacer una petición a la API:
   ```bash
   curl http://localhost:5000/api/tenants
   ```
2. En Grafana → Explore → Tempo → buscar por servicio conjunto-api.
3. La traza debe mostrar spans de api, y si llama a ai, aparecen en la misma traza.

Limpieza completa

```bash
docker compose down -v --rmi local
docker system prune -af --volumes
```

Variables de entorno

Todas se leen de .env. Ver .env.example para el listado completo.
Ninguna credencial va hardcodeada en docker-compose.yml.
