import asyncio,json,logging,os
import aio_pika,asyncpg
from prometheus_client import Counter,CollectorRegistry,start_http_server
from discovery_projector import project_discovery
from resilience import process_message
RABBIT_URL=os.getenv("RABBIT_URL","amqp://vigia:change-me@rabbitmq/");DB_DSN=os.getenv("DB_DSN","postgresql://vigia:change-me@postgres:5432/vigilancia")
# A private registry prevents duplicate timeseries when workers are loaded more than once
# by test harnesses or embedded diagnostics; the production HTTP endpoint exports this registry.
METRICS_REGISTRY=CollectorRegistry()
PROCESSED=Counter("worker_processed_total","Processed",["priority"],registry=METRICS_REGISTRY);ERRORS=Counter("worker_errors_total","Errors",registry=METRICS_REGISTRY)
OUTBOX_PUBLISHED=Counter("worker_outbox_published_total","Outbox rows published",registry=METRICS_REGISTRY);OUTBOX_FAILED=Counter("worker_outbox_publish_failures_total","Outbox publish failures",registry=METRICS_REGISTRY)
DEAD_LETTERED=Counter("worker_dead_lettered_total","Messages sent to dead-letter",registry=METRICS_REGISTRY)
log=logging.getLogger("worker")
REQUIRED_FIELDS=("event_id","device_id","type","priority","sequence_number","timestamp")
EVENTS_EXCHANGE="events.fanout"
# True cuando la migración 0004 (event_outbox) está aplicada. Si no, se usa el camino legado
# (publicación directa tras commit) para no romper despliegues sin migrar.
USE_OUTBOX=False

def validate_event(ev):
 """El evento es dato no confiable hasta validarlo: campos obligatorios y tipos mínimos."""
 if not isinstance(ev,dict):raise ValueError("event must be a JSON object")
 missing=[k for k in REQUIRED_FIELDS if k not in ev]
 if missing:raise KeyError(f"missing fields: {missing}")
 if not isinstance(ev["device_id"],str) or not 1<=len(ev["device_id"])<=128:raise ValueError("invalid device_id")
 if not isinstance(ev["timestamp"],(int,float)) or ev["timestamp"]<0:raise ValueError("invalid timestamp")
 if not isinstance(ev["sequence_number"],int) or ev["sequence_number"]<0:raise ValueError("invalid sequence_number")
 return ev

async def process(pool,ex,body):
 ev=validate_event(json.loads(body))
 async with pool.acquire() as c:
  async with c.transaction():
   inserted=await c.fetchval("""INSERT INTO events(event_id,device_id,zone,type,priority,sequence_number,ts,payload,signature) VALUES($1,$2,$3,$4,$5,$6,to_timestamp($7/1000.0),$8,$9) ON CONFLICT DO NOTHING RETURNING event_id""",ev["event_id"],ev["device_id"],ev.get("zone",""),ev["type"],ev["priority"],ev["sequence_number"],ev["timestamp"],json.dumps(ev.get("payload",{})),ev.get("signature"))
   await c.execute("INSERT INTO devices(device_id,zone,fw_version,last_seen,healthy) VALUES($1,$2,$3,to_timestamp($4/1000.0),true) ON CONFLICT(device_id) DO UPDATE SET zone=EXCLUDED.zone,last_seen=EXCLUDED.last_seen,healthy=true",ev["device_id"],ev.get("zone",""),ev.get("fw","unknown"),ev["timestamp"])
   if inserted:await c.execute("INSERT INTO device_events(device_id,event_id,kind) VALUES($1,$2,$3) ON CONFLICT DO NOTHING",ev["device_id"],ev["event_id"],ev["type"])
   await project_discovery(c,ev)
   # Outbox transaccional: la intención de publicar se confirma junto con el evento.
   if inserted and USE_OUTBOX:await c.execute("INSERT INTO event_outbox(aggregate_type,aggregate_id,exchange,payload) VALUES('event',$1,$2,$3::jsonb)",str(ev["event_id"]),EVENTS_EXCHANGE,body.decode("utf-8") if isinstance(body,(bytes,bytearray)) else body)
  PROCESSED.labels(ev["priority"]).inc()
  if inserted:
   if USE_OUTBOX:await relay_outbox(pool,ex)
   else:await ex.publish(aio_pika.Message(body=body,delivery_mode=aio_pika.DeliveryMode.PERSISTENT,content_type="application/json"),routing_key="")

async def relay_outbox(pool,ex,batch=100):
 """Publica filas pendientes del outbox. SKIP LOCKED permite varios workers sin duplicar.
 Si la publicación falla la fila queda pendiente con backoff; nunca se pierde el incidente."""
 published=0
 async with pool.acquire() as c:
  async with c.transaction():
   rows=await c.fetch("SELECT outbox_id,routing_key,payload FROM event_outbox WHERE published_at IS NULL AND available_at<=now() ORDER BY outbox_id LIMIT $1 FOR UPDATE SKIP LOCKED",batch)
   for r in rows:
    payload=r["payload"];body=payload if isinstance(payload,str) else json.dumps(payload,separators=(",",":"))
    try:
     await ex.publish(aio_pika.Message(body=body.encode("utf-8"),delivery_mode=aio_pika.DeliveryMode.PERSISTENT,content_type="application/json"),routing_key=r["routing_key"] or "")
    except Exception as exc:
     OUTBOX_FAILED.inc();log.warning("outbox publish failed (id=%s): %r",r["outbox_id"],exc)
     await c.execute("UPDATE event_outbox SET attempts=attempts+1,last_error=$2,available_at=now()+make_interval(secs=>LEAST(power(2,attempts),60)) WHERE outbox_id=$1",r["outbox_id"],str(exc)[:500])
     break
    await c.execute("UPDATE event_outbox SET published_at=now() WHERE outbox_id=$1",r["outbox_id"]);published+=1;OUTBOX_PUBLISHED.inc()
 return published

async def outbox_loop(pool,ex,interval=2.0):
 """Recupera filas dejadas por un proceso caído o por un fallo de publicación previo."""
 while True:
  try:await relay_outbox(pool,ex)
  except asyncio.CancelledError:raise
  except Exception:log.exception("outbox relay error")
  await asyncio.sleep(interval)

async def connect_retry(factory,what,attempts=30,delay=2.0):
 for i in range(attempts):
  try:return await factory()
  except Exception as exc:
   log.warning("%s no disponible (%s/%s): %r",what,i+1,attempts,exc);await asyncio.sleep(delay)
 raise RuntimeError(f"{what} unavailable after {attempts} attempts")

async def main():
 global USE_OUTBOX
 logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"))
 start_http_server(9100, registry=METRICS_REGISTRY)
 pool=await connect_retry(lambda:asyncpg.create_pool(DB_DSN,min_size=2,max_size=10),"postgres")
 conn=await connect_retry(lambda:aio_pika.connect_robust(RABBIT_URL),"rabbitmq");ch=await conn.channel();await ch.set_qos(prefetch_count=100)
 q=await ch.declare_queue("events.priority",durable=True,arguments={"x-max-priority":10,"x-queue-type":"quorum"});ex=await ch.declare_exchange(EVENTS_EXCHANGE,aio_pika.ExchangeType.FANOUT,durable=True)
 USE_OUTBOX=bool(await pool.fetchval("SELECT to_regclass('event_outbox') IS NOT NULL"))
 log.info("outbox transaccional: %s",USE_OUTBOX)
 relay=asyncio.create_task(outbox_loop(pool,ex)) if USE_OUTBOX else None
 async def handler(msg):await process(pool,ex,msg.body)
 try:
  async with q.iterator() as it:
   async for msg in it:
    outcome=await process_message(msg,handler,pool=pool,service="worker-pool",queue="events.priority")
    if outcome!="acked":ERRORS.inc()
    if outcome=="dead-lettered":DEAD_LETTERED.inc()
 finally:
  if relay:relay.cancel()
if __name__=="__main__":asyncio.run(main())
