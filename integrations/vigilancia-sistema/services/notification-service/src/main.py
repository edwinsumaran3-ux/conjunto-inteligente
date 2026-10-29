import asyncio,json,os
import aio_pika,httpx
from prometheus_client import Counter,start_http_server
RABBIT_URL=os.getenv("RABBIT_URL","amqp://vigia:change-me@rabbitmq/");SENT=Counter("notif_sent_total","Sent",["channel"]);FAILED=Counter("notif_failed_total","Failed",["channel"])
CHANNELS={k:v for k,v in {"webhook":os.getenv("NOTIFY_WEBHOOK_URL","")}.items() if v}
async def send(channel,url,payload):
 for i in range(4):
  try:
   async with httpx.AsyncClient(timeout=4) as c:r=await c.post(url,json=payload)
   if r.status_code<300:SENT.labels(channel).inc();return True
  except Exception:pass
  await asyncio.sleep(min(2**i,8))
 FAILED.labels(channel).inc();return False
async def main():
 start_http_server(9103);conn=await aio_pika.connect_robust(RABBIT_URL);ch=await conn.channel();ex=await ch.declare_exchange("alerts.fanout",aio_pika.ExchangeType.FANOUT,durable=True);q=await ch.declare_queue("notifications.q",durable=True);await q.bind(ex)
 async with q.iterator() as it:
  async for msg in it:
   async with msg.process(requeue=True):
    if not CHANNELS:
     await asyncio.sleep(5)  # evita reencolado a máxima velocidad mientras falta configuración
     raise RuntimeError("No notification channel configured")
    alert=json.loads(msg.body);await asyncio.gather(*(send(k,u,alert) for k,u in CHANNELS.items()))
if __name__=="__main__":asyncio.run(main())
