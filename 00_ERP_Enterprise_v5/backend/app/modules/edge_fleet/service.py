from __future__ import annotations
import hashlib,hmac,json
from datetime import datetime,timezone,timedelta

def canonical(v): return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,default=str)
def sha256(v): return hashlib.sha256(canonical(v).encode()).hexdigest()
def sign_manifest(manifest:dict,key:bytes)->str: return hmac.new(key,canonical(manifest).encode(),hashlib.sha256).hexdigest()
def verify_manifest(manifest,sig,key): return hmac.compare_digest(sign_manifest(manifest,key),sig)
def ota_allowed(current,target,ring,rollback=False):
    if rollback: return True
    if ring not in {'canary','pilot','production','emergency'}: return False
    if current==target: return False
    return bool(target.strip())
def watchdog_state(last_heartbeat,timeout_seconds,now=None):
    now=now or datetime.now(timezone.utc)
    if last_heartbeat is None: return 'safe'
    return 'safe' if (now-last_heartbeat).total_seconds()>timeout_seconds else 'armed'
def retry_at(attempts,base=2,max_seconds=300): return datetime.now(timezone.utc)+timedelta(seconds=min(max_seconds,base**max(0,attempts)))
def choose_parent(links):
    healthy=[x for x in links if x.get('status')=='healthy']
    return min(healthy,key=lambda x:(x.get('priority',100),x.get('latency_ms',1e9),x.get('packet_loss',1e9)),default=None)
