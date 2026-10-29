import asyncio,time
class TokenBucket:
 def __init__(self,rate_per_sec:int,burst:int): self.rate=rate_per_sec;self.burst=burst;self.tokens=float(burst);self.last=time.monotonic();self.lock=asyncio.Lock()
 async def allow(self)->bool:
  async with self.lock:
   now=time.monotonic();self.tokens=min(self.burst,self.tokens+(now-self.last)*self.rate);self.last=now
   if self.tokens<1:return False
   self.tokens-=1;return True
