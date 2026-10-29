import asyncio,json,os
import aio_pika,asyncpg
from prometheus_client import Counter,start_http_server
from resilience import process_message
RABBIT_URL=os.getenv("RABBIT_URL","amqp://vigia:change-me@rabbitmq/");DB_DSN=os.getenv("DB_DSN","postgresql://vigia:change-me@postgres:5432/vigilancia");CREATED=Counter("incident_core_updates_total","Incident updates")
async def main():
 start_http_server(9104);pool=await asyncpg.create_pool(DB_DSN);conn=await aio_pika.connect_robust(RABBIT_URL);ch=await conn.channel();ex=await ch.declare_exchange("incidents.fanout",aio_pika.ExchangeType.FANOUT,durable=True);alerts=await ch.declare_exchange("alerts.fanout",aio_pika.ExchangeType.FANOUT,durable=True);q=await ch.declare_queue("incident-core.q",durable=True);await q.bind(ex)
 async def handler(msg):
  ev=json.loads(msg.body)
  async with pool.acquire() as c: row=await c.fetchrow("UPDATE incidents SET updated_at=now(),details=details||$2::jsonb WHERE correlation_key=$1 RETURNING incident_id,severity,details",ev["correlation_key"],json.dumps(ev.get("details",{})))
  if row:
   CREATED.inc();payload=json.dumps({"incident_id":str(row["incident_id"]),"severity":row["severity"],"details":ev.get("details",{})}).encode();await alerts.publish(aio_pika.Message(body=payload,delivery_mode=aio_pika.DeliveryMode.PERSISTENT),routing_key="")
 async with q.iterator() as it:
  async for msg in it:
   await process_message(msg,handler,pool=pool,service="incident-core",queue="incident-core.q")
if __name__=="__main__":asyncio.run(main())
