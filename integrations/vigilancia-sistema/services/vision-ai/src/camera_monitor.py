import asyncio,time
from dataclasses import dataclass
from typing import Dict
@dataclass
class CameraState:
 cam_id:str;last_frame_ts:float=0;fps:float=0;latency_ms:float=0;storage_free_gb:float=0;healthy:bool=True;retries:int=0
class CameraMonitor:
 def __init__(self,fps_min=10,latency_max_ms=800,storage_min_gb=5,no_frame_timeout=5):self.fps_min=fps_min;self.lat_max=latency_max_ms;self.storage_min=storage_min_gb;self.no_frame=no_frame_timeout;self.cams:Dict[str,CameraState]={}
 def update(self,cam_id,fps,latency_ms,storage_gb):
  c=self.cams.setdefault(cam_id,CameraState(cam_id));c.last_frame_ts=time.time();c.fps=fps;c.latency_ms=latency_ms;c.storage_free_gb=storage_gb;c.healthy=fps>=self.fps_min and latency_ms<=self.lat_max and storage_gb>=self.storage_min
 async def supervise(self,emit):
  while True:
   await asyncio.sleep(5);now=time.time()
   for c in self.cams.values():
    if now-c.last_frame_ts>self.no_frame:await emit({"type":"CAMERA_OFFLINE","cam_id":c.cam_id,"priority":"SECURITY","payload":{"reason":"no_frames"}});c.retries+=1;await emit({"type":"CAMERA_FAILOVER","cam_id":c.cam_id,"priority":"SECURITY","payload":{"action":"switch_stream"}}) if c.retries>3 else None
    elif not c.healthy:await emit({"type":"CAMERA_DEGRADED","cam_id":c.cam_id,"priority":"ANOMALY","payload":c.__dict__})
