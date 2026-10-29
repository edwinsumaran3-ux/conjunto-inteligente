import httpx
class GatewayFailover:
 def __init__(self,peers,health_path="/healthz"):self.peers=[p.rstrip('/') for p in peers if p.strip()];self.health_path=health_path
 async def pick(self):
  async with httpx.AsyncClient(timeout=2) as c:
   for p in self.peers:
    try:
     if (await c.get(p+self.health_path)).status_code==200:return p
    except Exception:pass
  raise RuntimeError("No healthy peer")
