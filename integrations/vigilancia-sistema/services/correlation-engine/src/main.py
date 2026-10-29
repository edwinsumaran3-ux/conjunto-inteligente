import asyncio,json,os,time
import aio_pika,asyncpg,redis.asyncio as redis
from prometheus_client import Counter,start_http_server
from resilience import process_message
RABBIT_URL=os.getenv("RABBIT_URL","amqp://vigia:change-me@rabbitmq/");DB_DSN=os.getenv("DB_DSN","postgresql://vigia:change-me@postgres:5432/vigilancia");REDIS_URL=os.getenv("REDIS_URL","redis://redis:6379/0");WINDOW=30;INCIDENTS_EXCHANGE="incidents.fanout";USE_OUTBOX=False
CORR=Counter("corr_incidents_total","Incidents",["severity"])
class Correlator:
 def __init__(self,pool,r,ex):self.pool=pool;self.r=r;self.ex=ex
 async def ingest(self,ev):
  now=time.time();dev=ev["device_id"];typ=ev["type"];key=f"corr:{dev}:{typ}";await self.r.zadd(key,{ev["event_id"]:now});await self.r.expire(key,WINDOW*4)
  if typ=="TAMPER":await self.emit(f"tamper:{dev}","CRITICAL","TAMPER",{"trigger":ev})
  if typ=="MOTION" and await self.r.zcount(key,now-WINDOW,now)>=3:await self.emit(f"motion:{dev}:{int(now//WINDOW)}","ANOMALY","MOTION_BURST",{"device":dev})
  # CORRECCIÓN: antes bastaba que existieran las claves (TTL 4*WINDOW=120s) y se declaraba intrusión con
  # eventos separados hasta 2 minutos; ahora ambos deben caer dentro de la ventana de correlación (WINDOW).
  if typ in ("DOOR","MOTION") and await self.r.zcount(f"corr:{dev}:DOOR",now-WINDOW,now)>0 and await self.r.zcount(f"corr:{dev}:MOTION",now-WINDOW,now)>0:await self.emit(f"intrusion:{dev}:{int(now//WINDOW)}","SECURITY","INTRUSION",{"device":dev})
  if typ in ("LASER_TRIPWIRE","IR_BARRIER"):await self.emit(f"perimeter:{dev}:{int(now)}","SECURITY","PERIMETER_BREACH",{"device":dev,"zone":ev.get("zone",""),"sensor_type":typ})
 async def emit(self,key,severity,kind,details):
  body=json.dumps({"correlation_key":key,"severity":severity,"kind":kind,"details":details}).encode()
  async with self.pool.acquire() as c:
   async with c.transaction():
    row=await c.fetchrow("INSERT INTO incidents(correlation_key,severity,details) VALUES($1,$2,$3) ON CONFLICT DO NOTHING RETURNING incident_id",key,severity,json.dumps({"kind":kind,**details}))
    if row:
     payload=json.dumps({"correlation_key":key,"incident_id":str(row["incident_id"]),"severity":severity,"kind":kind,"details":details}).encode()
     # Outbox: el incidente y la intención de publicarlo se confirman juntos (antes, un fallo de publicación
     # tras el INSERT dejaba el incidente creado pero jamás notificado al orquestador).
     if USE_OUTBOX:await c.execute("INSERT INTO event_outbox(aggregate_type,aggregate_id,exchange,payload) VALUES('incident',$1,$2,$3::jsonb)",str(row["incident_id"]),INCIDENTS_EXCHANGE,payload.decode())
  if row:
   CORR.labels(severity).inc()
   if USE_OUTBOX:await relay_outbox(self.pool,self.ex)
   else:await self.ex.publish(aio_pika.Message(body=payload,delivery_mode=aio_pika.DeliveryMode.PERSISTENT,content_type="application/json"),routing_key="")
async def relay_outbox(pool,ex,batch=50):
 async with pool.acquire() as c:
  async with c.transaction():
   rows=await c.fetch("SELECT outbox_id,payload FROM event_outbox WHERE published_at IS NULL AND exchange=$2 AND available_at<=now() ORDER BY outbox_id LIMIT $1 FOR UPDATE SKIP LOCKED",batch,INCIDENTS_EXCHANGE)
   for r in rows:
    p=r["payload"];body=p if isinstance(p,str) else json.dumps(p)
    try:await ex.publish(aio_pika.Message(body=body.encode(),delivery_mode=aio_pika.DeliveryMode.PERSISTENT,content_type="application/json"),routing_key="")
    except Exception as exc:
     await c.execute("UPDATE event_outbox SET attempts=attempts+1,last_error=$2,available_at=now()+make_interval(secs=>LEAST(power(2,attempts),60)) WHERE outbox_id=$1",r["outbox_id"],str(exc)[:500]);break
    await c.execute("UPDATE event_outbox SET published_at=now() WHERE outbox_id=$1",r["outbox_id"])
async def outbox_loop(pool,ex,interval=2.0):
 while True:
  try:await relay_outbox(pool,ex)
  except asyncio.CancelledError:raise
  except Exception:pass
  await asyncio.sleep(interval)
async def main():
 global USE_OUTBOX
 start_http_server(9101);pool=await asyncpg.create_pool(DB_DSN);r=redis.from_url(REDIS_URL,decode_responses=True);conn=await aio_pika.connect_robust(RABBIT_URL);ch=await conn.channel();await ch.set_qos(prefetch_count=50);ex=await ch.declare_exchange("events.fanout",aio_pika.ExchangeType.FANOUT,durable=True);iex=await ch.declare_exchange("incidents.fanout",aio_pika.ExchangeType.FANOUT,durable=True);q=await ch.declare_queue("correlation.q",durable=True);await q.bind(ex);corr=Correlator(pool,r,iex)
 USE_OUTBOX=bool(await pool.fetchval("SELECT to_regclass('event_outbox') IS NOT NULL"));relay=asyncio.create_task(outbox_loop(pool,iex)) if USE_OUTBOX else None
 async with q.iterator() as it:
  async def handler(m):await corr.ingest(json.loads(m.body))
  async for msg in it:
   await process_message(msg,handler,pool=pool,service="correlation-engine",queue="correlation.q")
if __name__=="__main__":asyncio.run(main())
