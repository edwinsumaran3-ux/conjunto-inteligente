import time
class TamperDetector:
 def __init__(self,window_s=60):self.window=window_s;self.buffer=[]
 def push(self,ev):ev["_ts"]=time.time();self.buffer.append(ev);cutoff=time.time()-self.window;self.buffer=[e for e in self.buffer if e["_ts"]>=cutoff]
 def analyze(self,device_id):
  recent=[e for e in self.buffer if e.get("device_id")==device_id];kinds={e.get("type") for e in recent};signals=(3 if "TAMPER" in kinds else 0)+(2 if "CAMERA_OFFLINE" in kinds else 0)+(1 if "SENSOR_FAIL" in kinds else 0)+(2 if "HEARTBEAT_LOST" in kinds else 0)
  return {"classification":"DEVICE_TAMPERING","severity":"CRITICAL","signals":list(kinds)} if signals>=4 else {"classification":"NORMAL","severity":"INFO"}
