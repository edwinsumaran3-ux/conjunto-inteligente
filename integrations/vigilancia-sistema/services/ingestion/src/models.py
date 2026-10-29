import json
from typing import Any, Literal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, field_validator

Priority = Literal["CRITICAL","SECURITY","ANOMALY","TELEMETRY"]
EventType = Literal["MOTION","TAMPER","DOOR","CAMERA_OFFLINE","CAMERA_DEGRADED","CAMERA_FAILOVER","SENSOR_FAIL","HEARTBEAT","HEARTBEAT_LOST","ANOMALY","MANUAL","AI_UNCERTAIN","LASER_TRIPWIRE","IR_BARRIER","PERIMETER_BREACH","DEVICE_DISCOVERED"]
class EventIn(BaseModel):
    model_config=ConfigDict(extra="forbid")
    event_id: UUID; device_id: str=Field(min_length=1,max_length=128); sequence_number:int=Field(ge=0)
    timestamp:int=Field(ge=0); type:EventType; priority:Priority="TELEMETRY"; zone:str=""; payload:dict[str,Any]={}; signature:str|None=None

    @field_validator("payload")
    @classmethod
    def _payload_size(cls, v):
        # Misma cota que ck_events_payload_size en la BD: se rechaza en el borde en vez de fallar luego en el worker.
        if len(json.dumps(v, separators=(",", ":"), default=str)) > 65536:
            raise ValueError("payload demasiado grande (máx. 64 KiB)")
        return v
