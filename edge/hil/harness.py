from __future__ import annotations
import random,time
from dataclasses import dataclass
from datetime import datetime,timezone,timedelta
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'00_ERP_Enterprise_v5/backend'))
from app.modules.edge_fleet.service import watchdog_state
@dataclass
class SimDevice:
    device_id:str; state:str='armed'; last_heartbeat:datetime|None=None; seq:int=0
class HIL:
    """Deterministic hardware-in-the-loop style simulator; it never touches real actuators."""
    def __init__(self,seed=7): self.rng=random.Random(seed); self.devices={}
    def add(self,id): self.devices[id]=SimDevice(id,last_heartbeat=datetime.now(timezone.utc))
    def fault(self,id,fault):
        d=self.devices[id]
        if fault=='network_loss': d.last_heartbeat=datetime.now(timezone.utc)-timedelta(seconds=999)
        elif fault=='duplicate': d.seq=max(0,d.seq-1)
        elif fault=='clock_skew': d.last_heartbeat=datetime.now(timezone.utc)-timedelta(seconds=120)
        elif fault=='gateway_failure': d.state='safe'
        else: raise ValueError(fault)
    def reconcile(self,id,timeout=60):
        d=self.devices[id]; d.state=watchdog_state(d.last_heartbeat,timeout); return d.state
