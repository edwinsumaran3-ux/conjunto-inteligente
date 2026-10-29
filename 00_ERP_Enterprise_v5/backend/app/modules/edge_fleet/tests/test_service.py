from datetime import datetime,timezone,timedelta
from backend.app.modules.edge_fleet.service import *
def test_manifest_signature():
 m={'version':'1.2.3','sha256':'a'*64}; k=b'x'*32; s=sign_manifest(m,k); assert verify_manifest(m,s,k); assert not verify_manifest(m,s[:-1]+'0',k)
def test_watchdog_and_ota():
 n=datetime.now(timezone.utc); assert watchdog_state(n-timedelta(seconds=61),60,n)=='safe'; assert watchdog_state(n,60,n)=='armed'; assert ota_allowed('1','2','canary'); assert not ota_allowed('1','1','canary')
def test_backoff_and_parent():
 a=retry_at(3); assert a>datetime.now(timezone.utc); assert choose_parent([{'status':'healthy','priority':20},{'status':'healthy','priority':10}])['priority']==10
