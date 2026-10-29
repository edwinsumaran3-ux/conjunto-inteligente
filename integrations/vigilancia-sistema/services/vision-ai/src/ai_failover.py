import httpx
class AIFailover:
 def __init__(self,models,min_confidence=.65,timeout=2):self.models=[m.strip().rstrip('/') for m in models if m.strip()];self.min_conf=min_confidence;self.timeout=timeout
 async def infer(self,image_ref):
  errors=[]
  async with httpx.AsyncClient(timeout=self.timeout) as c:
   for m in self.models:
    try:
     r=await c.post(f"{m}/infer",json={"image":image_ref});r.raise_for_status();d=r.json();d["model"]=m;d["uncertain"]=float(d.get("confidence",0))<self.min_conf;return {"available":True,**d}
    except Exception as e:errors.append({"model":m,"error":str(e)})
  return {"available":False,"uncertain":True,"result":None,"errors":errors}
