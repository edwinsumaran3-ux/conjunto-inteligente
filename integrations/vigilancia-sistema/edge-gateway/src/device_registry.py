import time
from dataclasses import dataclass,field
@dataclass
class DeviceState:
 device_id:str;last_seen:float=0;healthy:bool=True;missed_heartbeats:int=0;fw_version:str="unknown";zone:str="unknown";metadata:dict=field(default_factory=dict)
class DeviceRegistry:
 def __init__(self,unhealthy_threshold=3):self._devices={};self.threshold=unhealthy_threshold
 def heartbeat(self,device_id,zone,fw="unknown",metadata=None):
  d=self._devices.setdefault(device_id,DeviceState(device_id));d.last_seen=time.time();d.missed_heartbeats=0;d.healthy=True;d.zone=zone;d.fw_version=fw;d.metadata=metadata or d.metadata
 def sweep(self,timeout_s=60):
  now=time.time();out=[]
  for d in self._devices.values():
   if now-d.last_seen>timeout_s:d.missed_heartbeats+=1
   if d.missed_heartbeats>=self.threshold and d.healthy:d.healthy=False;out.append(d)
  return out
 def all(self):return list(self._devices.values())
