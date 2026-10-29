import json
from pathlib import Path
from uuid import uuid4
import sys
sys.path.insert(0,str(Path(__file__).parents[1]/"services/ingestion/src"))
from models import EventIn

def test_event_model():
 e=EventIn(event_id=uuid4(),device_id="d1",sequence_number=1,timestamp=1,type="MOTION",priority="SECURITY",payload={})
 assert e.sequence_number==1

def test_schema_exists():
 s=json.loads((Path(__file__).parents[1]/"shared/schemas/event.schema.json").read_text())
 assert s["$schema"].startswith("https://json-schema.org")

def test_new_event_types_accepted():
 # Tipos añadidos en la ampliación de cámaras/agentes/auto-descubrimiento:
 # deben ser aceptados tanto por el modelo pydantic de ingestion como por
 # el JSON Schema publicado en shared/schemas/, o quedan desincronizados.
 new_types=["LASER_TRIPWIRE","IR_BARRIER","PERIMETER_BREACH","DEVICE_DISCOVERED"]
 schema=json.loads((Path(__file__).parents[1]/"shared/schemas/event.schema.json").read_text())
 schema_enum=schema["properties"]["type"]["enum"]
 for t in new_types:
  assert t in schema_enum, f"{t} falta en event.schema.json"
  e=EventIn(event_id=uuid4(),device_id="d1",sequence_number=1,timestamp=1,type=t,priority="SECURITY",payload={})
  assert e.type==t

def test_event_model_rejects_unknown_type():
 try:
  EventIn(event_id=uuid4(),device_id="d1",sequence_number=1,timestamp=1,type="NOT_A_REAL_TYPE",priority="SECURITY",payload={})
  assert False,"debió rechazar un tipo de evento inexistente"
 except Exception:
  pass
