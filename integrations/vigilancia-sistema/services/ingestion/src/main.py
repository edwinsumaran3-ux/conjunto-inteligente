import json,os,asyncio
import aio_pika,asyncpg
import hmac
from fastapi import FastAPI,HTTPException,Query,Header
from fastapi.responses import Response
from prometheus_client import Counter,Gauge,generate_latest,CONTENT_TYPE_LATEST
from models import EventIn
from idempotency import IdempotencyStore
from priority_queue import priority_of
from rate_limit import TokenBucket
from backpressure import Backpressure
from security_headers import SecurityHeadersMiddleware
from correlation_id import CorrelationIdMiddleware
RABBIT_URL=os.getenv("RABBIT_URL","amqp://vigia:change-me@rabbitmq/");DB_DSN=os.getenv("DB_DSN","postgresql://vigia:change-me@postgres:5432/vigilancia")
INGEST_API_KEY=os.getenv("INGEST_API_KEY","");REDIS_ERR=Counter("ingest_redis_errors_total","Redis idempotency errors (degraded to PostgreSQL idempotency)")
QUEUE="events.priority";EX="events.fanout";app=FastAPI(title="Vigilancia Ingestion",version="2.0.0")
app.add_middleware(CorrelationIdMiddleware);app.add_middleware(SecurityHeadersMiddleware)
idem=IdempotencyStore();bucket=TokenBucket(int(os.getenv("RATE_LIMIT_RPS","2000")),int(os.getenv("RATE_LIMIT_BURST","5000")));bp=Backpressure(int(os.getenv("MAX_QUEUE","100000")))
ING=Counter("ingest_events_total","Events accepted",["priority"]);DUP=Counter("ingest_duplicates_total","Duplicate events");REJ=Counter("ingest_rejected_total","Rejected events",["reason"]);QSIZE=Gauge("ingest_queue_size","Queue depth")
channel=None;queue=None;db=None
async def queue_depth():
 try:
  d=await queue.declare(passive=True);QSIZE.set(d.message_count);bp.update(d.message_count);return d.message_count
 except Exception:return 0
@app.on_event("startup")
async def startup():
 global channel,queue,db
 for _ in range(30):
  try:
   db=await asyncpg.create_pool(DB_DSN,min_size=2,max_size=10)
   conn=await aio_pika.connect_robust(RABBIT_URL);channel=await conn.channel();await channel.set_qos(prefetch_count=200)
   queue=await channel.declare_queue(QUEUE,durable=True,arguments={"x-max-priority":10,"x-queue-type":"quorum"})
   await channel.declare_exchange(EX,aio_pika.ExchangeType.FANOUT,durable=True);app.state.conn=conn;break
  except Exception as e:
   await asyncio.sleep(2)
 else:raise RuntimeError("dependencies unavailable")
@app.on_event("shutdown")
async def shutdown():
 if db:await db.close()
 if getattr(app.state,"conn",None):await app.state.conn.close()
@app.post("/ingest")
async def ingest(event:EventIn,x_ingest_key:str|None=Header(default=None)):
 # Si INGEST_API_KEY está definida, solo el edge-gateway (que la conoce) puede inyectar eventos.
 if INGEST_API_KEY and not (x_ingest_key and hmac.compare_digest(x_ingest_key,INGEST_API_KEY)):REJ.labels("auth").inc();raise HTTPException(401,"ingest key required")
 if not await bucket.allow():REJ.labels("rate").inc();raise HTTPException(429,"rate limited")
 await queue_depth()
 if not bp.should_accept(event.model_dump(mode="json")):REJ.labels("backpressure").inc();raise HTTPException(503,"backpressure")
 eid=str(event.event_id)
 # redis-py es síncrono: se ejecuta en un hilo para no bloquear el event loop. Si Redis cae se degrada:
 # PostgreSQL (UNIQUE event_id) sigue siendo la autoridad de idempotencia, no se rechaza el evento.
 claimed=True
 try:claimed=await asyncio.to_thread(idem.claim,eid)
 except Exception:REDIS_ERR.inc()
 if not claimed:DUP.inc();return {"status":"DUPLICATE","event_id":eid}
 try:
  body=json.dumps(event.model_dump(mode="json"),separators=(",",":"),sort_keys=True).encode()
  msg=aio_pika.Message(body=body,priority=10-priority_of(event.model_dump()),delivery_mode=aio_pika.DeliveryMode.PERSISTENT,message_id=eid,content_type="application/json")
  await channel.default_exchange.publish(msg,routing_key=QUEUE);ING.labels(event.priority).inc();return {"status":"OK","event_id":eid}
 except Exception:
  try:await asyncio.to_thread(idem.release,eid)
  except Exception:pass
  raise HTTPException(503,"queue unavailable")
@app.get("/healthz")
async def healthz():
 try:await queue_depth();await db.fetchval("SELECT 1");return {"status":"ok"}
 except Exception:raise HTTPException(503,"degraded")
@app.get("/events")
async def events(limit:int=Query(100,ge=1,le=500),device_id:str|None=None):
 q="SELECT event_id,device_id,zone,type,priority,sequence_number,ts,payload,received_at FROM events";args=[]
 if device_id:q+=" WHERE device_id=$1";args.append(device_id)
 q+=f" ORDER BY ts DESC LIMIT ${len(args)+1}";args.append(limit)
 rows=await db.fetch(q,*args);return [dict(r) for r in rows]
@app.get("/incidents")
async def incidents(limit:int=Query(100,ge=1,le=500)):
 rows=await db.fetch("SELECT incident_id,correlation_key,severity,status,created_at,updated_at,details FROM incidents ORDER BY created_at DESC LIMIT $1",limit);return [dict(r) for r in rows]
@app.get("/metrics")
def metrics():return Response(generate_latest(),media_type=CONTENT_TYPE_LATEST)
