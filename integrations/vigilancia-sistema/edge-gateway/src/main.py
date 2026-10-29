import asyncio,json,os,time
from fastapi import FastAPI,HTTPException
from prometheus_client import Counter,Gauge,generate_latest,CONTENT_TYPE_LATEST
from fastapi.responses import Response
import paho.mqtt.client as mqtt
import aio_pika
from device_registry import DeviceRegistry
from local_rule_engine import LocalRuleEngine
from failover import GatewayFailover
from sensor_mesh import SensorMesh
from device_autodiscovery import DeviceAutoDiscovery, DiscoveredDevice
from security_headers import SecurityHeadersMiddleware
from durable_buffer import DurableBuffer
from correlation_id import CorrelationIdMiddleware
GATEWAY_ID=os.getenv("GATEWAY_ID","edge-01");MQTT_HOST=os.getenv("MQTT_HOST","mosquitto");MQTT_PORT=int(os.getenv("MQTT_PORT","1883"));PEERS=os.getenv("PEERS","http://ingestion:8000").split(",");BUFFER_PATH=os.getenv("BUFFER_PATH",f"/var/lib/edge/{GATEWAY_ID}/buffer.jsonl")
RABBIT_URL=os.getenv("RABBIT_URL","amqp://vigia:change-me@rabbitmq/")
buffer=DurableBuffer(BUFFER_PATH,int(os.getenv("BUFFER_MAX_EVENTS","50000")));DROPPED=Counter("edge_buffer_dropped_total","Eventos descartados por buffer lleno");REJECTED=Counter("edge_events_rejected_total","Eventos rechazados de forma permanente por el servidor");flush_lock=None
os.makedirs(os.path.dirname(BUFFER_PATH),exist_ok=True);app=FastAPI(title=f"Edge Gateway {GATEWAY_ID}");app.add_middleware(CorrelationIdMiddleware);app.add_middleware(SecurityHeadersMiddleware);registry=DeviceRegistry();rules=LocalRuleEngine();failover=GatewayFailover(PEERS);mesh=SensorMesh();discovery=DeviceAutoDiscovery();EVENTS=Counter("edge_events_in_total","Events",["type","priority"]);FWD=Counter("edge_events_forwarded_total","Forwarded");BUF=Gauge("edge_local_buffer_size","Local buffer");MODE=Gauge("edge_mode","0 online 1 degraded");CASCADE=Counter("edge_cascade_commands_total","Comandos de cascada cámara-sensor emitidos");loop=None;mqtt_client=None

def append_local(e):
 before=buffer.dropped;buffer.append(e);BUF.set(len(buffer))
 if buffer.dropped>before:DROPPED.inc(buffer.dropped-before)
async def forward_ex(e):
 """Devuelve (resultado|None, rechazo_permanente). 4xx (salvo 408/429) no mejora reintentando."""
 try:
  peer=await failover.pick()
  import httpx
  hdrs={"X-Ingest-Key":os.environ["INGEST_API_KEY"]} if os.getenv("INGEST_API_KEY") else {}
  async with httpx.AsyncClient(timeout=3) as c:r=await c.post(peer+"/ingest",json=e,headers=hdrs)
  if r.status_code in (200,202):FWD.inc();return r.json(),False
  if 400<=r.status_code<500 and r.status_code not in (408,429):return None,True
 except Exception:pass
 return None,False
async def forward(e):
 result,_=await forward_ex(e);return result
async def flush():
 global flush_lock
 if flush_lock is None:flush_lock=asyncio.Lock()
 if flush_lock.locked():return  # un solo flush a la vez
 async with flush_lock:
  snapshot=buffer.snapshot()
  if not snapshot:BUF.set(len(buffer));return
  remaining=[];rejected=[];corrupt=[]
  for line in snapshot[:int(os.getenv("FLUSH_BATCH","500"))]:
   try:ev=json.loads(line)
   except Exception:corrupt.append(line);continue
   result,permanent=await forward_ex(ev)
   if result is not None:continue
   if permanent:REJECTED.inc();rejected.append(line)
   else:remaining.append(line)
  sent=snapshot[:int(os.getenv("FLUSH_BATCH","500"))]
  # lo no intentado en este lote (cola larga) se conserva tal cual
  remaining.extend(snapshot[len(sent):])
  buffer.commit_flush(snapshot,remaining,rejected,corrupt);BUF.set(len(buffer))
def on_connect(client,userdata,flags,reason_code,properties=None):
 # Resuscribir en cada (re)conexión: con sesión limpia las suscripciones se pierden al caer el broker.
 try:client.subscribe("events/ingest",qos=1)
 except Exception:pass
BG_TASKS=[]
def on_message(client,userdata,msg):
 global loop
 try:e=json.loads(msg.payload.decode());EVENTS.labels(e.get("type","?"),e.get("priority","TELEMETRY")).inc()
 except Exception:return
 if e.get("type")=="HEARTBEAT":registry.heartbeat(e.get("device_id",""),e.get("zone",""),e.get("fw","unknown"),e.get("metadata"));return
 if not e.get("event_id"):return
 # Preserve raw event for central processing; local rules are additional actions, not replacements.
 if loop is None:return  # aún no arrancó el loop asyncio; el dispositivo reintentará (sin ACK)
 asyncio.run_coroutine_threadsafe(handle(e),loop)
async def handle(e):
 actions=rules.process(e)
 if e.get("type") in ("LASER_TRIPWIRE","IR_BARRIER"):
  for cmd in mesh.cascade_commands(e.get("device_id",""),e.get("zone","")):
   mqtt_client.publish(cmd["topic"],json.dumps(cmd["payload"]),qos=1);CASCADE.inc()
 result,permanent=await forward_ex(e)
 if permanent:REJECTED.inc();status="REJECTED"  # no se almacena un evento que el servidor rechaza por inválido
 elif result is None:
  MODE.set(1);append_local(e);status="BUFFERED"
 else:MODE.set(0);status=result.get("status","OK")
 # Device must receive ACK for the original event id; BUFFERED is valid because event remains durable locally.
 mqtt_client.publish("events/ack",json.dumps({"event_id":e["event_id"],"status":status}),qos=1)
 if actions and any(a.get("action")=="SOUND_ALARM" for a in actions):mqtt_client.publish("local/alarm",json.dumps(e),qos=1)
@app.on_event("startup")
async def startup():
 global loop,mqtt_client
 loop=asyncio.get_running_loop();mqtt_client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id=GATEWAY_ID)
 # CORRECCIÓN CRÍTICA: el callback on_message existía pero nunca se asignaba al cliente, por lo que los
 # eventos de los ESP32 llegaban al broker y el gateway jamás los procesaba ni los reenviaba.
 mqtt_client.on_message=on_message;mqtt_client.on_connect=on_connect
 for attempt in range(30):  # el edge debe arrancar aunque el broker tarde (autonomía de borde)
  try:mqtt_client.connect(MQTT_HOST,MQTT_PORT,60);break
  except Exception:await asyncio.sleep(2)
 else:raise RuntimeError("mqtt broker unavailable")
 mqtt_client.subscribe("events/ingest",qos=1);mqtt_client.loop_start();BG_TASKS.extend([asyncio.create_task(periodic()),asyncio.create_task(consume_actions())]);BUF.set(len(buffer))
async def consume_actions():
 # Puente best-effort: si RabbitMQ no está disponible el gateway sigue operando
 # localmente (autonomía de borde); solo se pierden órdenes remotas aprobadas
 # hasta que la conexión se restablezca.
 while True:
  try:
   conn=await aio_pika.connect_robust(RABBIT_URL);ch=await conn.channel();ex=await ch.declare_exchange("actions.fanout",aio_pika.ExchangeType.FANOUT,durable=True);q=await ch.declare_queue(f"edge.{GATEWAY_ID}.actions.q",durable=True);await q.bind(ex)
   async with q.iterator() as it:
    async for msg in it:
     try:action=json.loads(msg.body);dev=str(action.get("target_device_id") or "broadcast")
     except Exception:await msg.reject(requeue=False);continue  # mensaje venenoso: no se reencola sin fin
     if "/" in dev or "+" in dev or "#" in dev:await msg.reject(requeue=False);continue  # evita inyección de topics MQTT
     mqtt_client.publish(f"actions/execute/{dev}",json.dumps(action),qos=1);await msg.ack()
  except Exception:
   await asyncio.sleep(5)
@app.on_event("shutdown")
async def shutdown():
 for t in BG_TASKS:t.cancel()
 if mqtt_client:mqtt_client.loop_stop();mqtt_client.disconnect()
async def periodic():
 while True:
  await asyncio.sleep(10)
  try:  # una excepción puntual no debe detener para siempre la detección de timeouts ni el reenvío del buffer
   for d in registry.sweep(60):await handle({"event_id":str(__import__('uuid').uuid4()),"device_id":d.device_id,"sequence_number":0,"timestamp":int(time.time()*1000),"type":"SENSOR_FAIL","priority":"ANOMALY","zone":d.zone,"payload":{"reason":"heartbeat_timeout"}})
   await flush()
  except asyncio.CancelledError:raise
  except Exception:pass
@app.get("/healthz")
def healthz():return {"status":"ok","gateway":GATEWAY_ID,"devices":len(registry.all())}
@app.get("/devices")
def devices():return [d.__dict__ for d in registry.all()]
@app.post("/discovery/scan")
async def discovery_scan(body:dict):
 addresses=body.get("addresses",[]);zone=body.get("zone","")
 if not addresses:raise HTTPException(400,"addresses requerido")
 found=await discovery.scan(addresses,zone)
 for d in found:
  ev={"event_id":str(__import__('uuid').uuid4()),"device_id":d.device_id,"sequence_number":0,"timestamp":int(time.time()*1000),"type":"DEVICE_DISCOVERED","priority":"TELEMETRY","zone":zone,"payload":{"device_class":d.device_class,"vendor":d.vendor,"model":d.model,"protocol":d.protocol,"address":d.address,"compatibility":d.compatibility,"auto_connected":d.auto_connected,"stream_url":d.stream_url}}
  await forward(ev)
 return [d.__dict__ for d in found]
@app.get("/discovery/devices")
def discovery_devices():return [d.__dict__ for d in discovery.all()]
@app.post("/mesh/link")
def mesh_link(body:dict):
 sensor_id=body.get("sensor_id");cameras=body.get("camera_ids",[])
 if not sensor_id or not cameras:raise HTTPException(400,"sensor_id y camera_ids requeridos")
 mesh.register_link(sensor_id,cameras);return {"sensor_id":sensor_id,"neighbors":mesh.neighbors(sensor_id)}
@app.get("/mesh/topology")
def mesh_topology():return mesh._map
@app.get("/metrics")
def metrics():return Response(generate_latest(),media_type=CONTENT_TYPE_LATEST)
