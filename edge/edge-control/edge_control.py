from __future__ import annotations
import hashlib,hmac,json,sqlite3,time
from datetime import datetime,timezone
from pathlib import Path

SAFE={'armed','safe','kill_switch','quarantined'}
STOP_ONLY={'safe_state','stop_pump','stop_drone_mission','lock'}

def canon(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sig(env,key): return hmac.new(key,canon(env),hashlib.sha256).hexdigest()
def verify(env,signature,key): return hmac.compare_digest(sig(env,key),signature)

class EdgeControl:
    def __init__(self,db_path:str,key:bytes,capabilities:list[str]):
        self.db=sqlite3.connect(db_path); self.db.execute('PRAGMA journal_mode=WAL'); self.db.execute('CREATE TABLE IF NOT EXISTS state(k TEXT PRIMARY KEY,v TEXT NOT NULL)'); self.db.execute('CREATE TABLE IF NOT EXISTS replay(nonce TEXT PRIMARY KEY,seq INTEGER NOT NULL)'); self.db.commit(); self.key=key; self.cap=set(capabilities)
    def state(self): return self.db.execute("SELECT v FROM state WHERE k='safety'").fetchone()[0] if self.db.execute("SELECT 1 FROM state WHERE k='safety'").fetchone() else 'armed'
    def set_state(self,state):
        if state not in SAFE: raise ValueError('invalid safety state')
        self.db.execute("INSERT INTO state(k,v) VALUES('safety',?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",(state,)); self.db.commit()
    def accept(self,envelope,signature):
        if not verify(envelope,signature,self.key): return False,'invalid_signature'
        if envelope['command_type'] not in self.cap: return False,'capability_denied'
        if self.state() in ('kill_switch','quarantined') and envelope['command_type']!='safe_state': return False,'safety_blocked'
        if self.state()=='safe' and envelope['command_type'] not in STOP_ONLY: return False,'safe_state_blocked'
        raw_exp=envelope['expires_at']
        try:
            exp=datetime.fromisoformat(raw_exp.replace('Z','+00:00')).timestamp() if isinstance(raw_exp,str) else float(raw_exp)
        except (TypeError,ValueError): return False,'invalid_expiry'
        if exp <= time.time(): return False,'expired'
        nonce=envelope['nonce']; seq=int(envelope['sequence'])
        if self.db.execute('SELECT 1 FROM replay WHERE nonce=?',(nonce,)).fetchone(): return False,'replay'
        last=self.db.execute('SELECT MAX(seq) FROM replay').fetchone()[0] or 0
        if seq<=last: return False,'sequence_replay'
        self.db.execute('INSERT INTO replay(nonce,seq) VALUES(?,?)',(nonce,seq)); self.db.commit(); return True,'accepted'
