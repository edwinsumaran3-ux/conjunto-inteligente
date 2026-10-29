import os
from fastapi import FastAPI,UploadFile,File,HTTPException
from prometheus_client import Counter,make_asgi_app
from ai_failover import AIFailover
MODELS=os.getenv("AI_MODELS","").split(",");app=FastAPI(title="Vision AI Gateway");ai=AIFailover(MODELS);OK=Counter("ai_ok_total","OK");UNC=Counter("ai_uncertain_total","Uncertain");DOWN=Counter("ai_down_total","Down")
@app.get("/healthz")
def health():return {"status":"ok","models":len(ai.models)}
@app.post("/infer")
async def infer(file:UploadFile=File(...)):
 data=await file.read();
 if len(data)>10_000_000:raise HTTPException(413,"image too large")
 # The gateway forwards a temporary local reference only to trusted model endpoints.
 import tempfile,os as _os
 fd,path=tempfile.mkstemp(prefix="vigia-",suffix=".bin");_os.write(fd,data);_os.close(fd)
 try:
  res=await ai.infer(path);(DOWN if not res.get("available") else UNC if res.get("uncertain") else OK).inc();return res
 finally:
  try:_os.unlink(path)
  except OSError:pass
app.mount("/metrics",make_asgi_app())
