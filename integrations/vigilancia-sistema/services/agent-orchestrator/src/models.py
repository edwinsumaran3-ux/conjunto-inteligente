from typing import Any, Literal
from pydantic import BaseModel, ConfigDict

Severity = Literal["LOW","MEDIUM","HIGH","CRITICAL"]
ActionType = Literal["SOUND_ALARM","LOCK_ACCESS","UNLOCK_ACCESS","NOTIFY_AUTHORITIES","FOCUS_CAMERA","START_RECORDING","SAFE_HOLD","NO_OP"]
Decision = Literal["PENDING","APPROVED","REJECTED","EXPIRED"]

class Incident(BaseModel):
    model_config=ConfigDict(extra="allow")
    incident_id: str; correlation_key: str; severity: str; kind: str|None=None; details: dict[str,Any]={}

class ActionProposal(BaseModel):
    agent_name: str; action_type: ActionType; severity: Severity
    target_device_id: str|None=None; zone: str|None=None
    rationale: str; payload: dict[str,Any]={}
    requires_human_approval: bool=False

class ApprovalDecisionIn(BaseModel):
    decided_by: str
    decision: Literal["APPROVED","REJECTED"]
    operator_signature: str|None=None
