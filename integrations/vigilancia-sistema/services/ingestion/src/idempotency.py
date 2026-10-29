import os,time,redis
class IdempotencyStore:
 def __init__(self):
  self.r=redis.Redis(host=os.getenv("REDIS_HOST","redis"),port=int(os.getenv("REDIS_PORT","6379")),password=os.getenv("REDIS_PASSWORD") or None,decode_responses=True,socket_connect_timeout=2,socket_timeout=2)
  self.ttl=int(os.getenv("IDEMPOTENCY_TTL_S","604800"))
 def claim(self,event_id:str)->bool:return bool(self.r.set(f"idem:{event_id}",str(time.time()),nx=True,ex=self.ttl))
 def release(self,event_id:str)->None:self.r.delete(f"idem:{event_id}")
