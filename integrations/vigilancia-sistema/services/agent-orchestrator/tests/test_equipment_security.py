import os,sys,asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from equipment_contracts import EquipmentCommand, EquipmentType
from equipment_registry import EquipmentRegistry

class Adapter:
    equipment_id="d1"; equipment_type=EquipmentType.DRONE
    @property
    def is_connected(self): return False
    def authorize(self,c): raise AssertionError("must reject before authorize")
    async def execute(self,c): raise AssertionError
    async def get_telemetry(self): raise AssertionError
    async def emergency_stop(self): pass

def test_placeholder_signature_is_rejected():
    r=EquipmentRegistry(); r.register(Adapter())
    c=EquipmentCommand("a","n",EquipmentType.DRONE,"d1","observe",{},0,9999999999,"system","system-issued:unverified")
    out=asyncio.run(r.dispatch(c))
    assert out.accepted is False and out.reason=="missing-verified-signature"
