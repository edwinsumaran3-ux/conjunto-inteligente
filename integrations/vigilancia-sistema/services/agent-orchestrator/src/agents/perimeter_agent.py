from agents.base_agent import BaseAgent
from models import Incident, ActionProposal

class PerimeterAgent(BaseAgent):
    """Especializado en el perímetro físico: barreras láser/IR y su cadena de
    cámaras vecinas. La reorientación inmediata ya ocurre localmente en el
    borde (ver `edge-gateway/src/sensor_mesh.py`, autonomía de borde); este
    agente audita el mismo incidente en el backend central y confirma la
    misma acción no destructiva, quedando registrada en `agent_actions`
    aunque el borde ya haya actuado sin esperarlo.

    Cuando una barrera se interrumpe, este agente no espera confirmación
    humana para reorientar cámaras (acción reversible y no destructiva);
    sí la exige para cualquier acción de bloqueo o sirena, que delega al
    IntrusionAgent mediante el mismo incidente si la severidad escala.
    """

    name = "perimeter-agent"

    def relevant(self, incident: Incident) -> bool:
        return (incident.kind or "").upper() in ("PERIMETER_BREACH","LASER_TRIPWIRE","IR_BARRIER")

    def assess(self, incident: Incident) -> ActionProposal | None:
        device = incident.details.get("device") or incident.details.get("device_id")
        zone = incident.details.get("zone","")
        return ActionProposal(
            agent_name=self.name, action_type="FOCUS_CAMERA", severity="HIGH",
            target_device_id=device, zone=zone,
            rationale="Barrera láser/IR interrumpida: se reorientan las cámaras contiguas al punto exacto de intrusión (cascade event bus).",
            payload={"cascade":True,"source_sensor":device}, requires_human_approval=False,
        )
