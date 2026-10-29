from agents.base_agent import BaseAgent
from models import Incident, ActionProposal

class IntrusionAgent(BaseAgent):
    """Especializado en incidentes de intrusión (INTRUSION, TAMPER, MOTION_BURST).

    Propone bloqueo de accesos, sirena y notificación a autoridades.
    Toda acción con impacto físico (sirena, bloqueo) se marca como
    `requires_human_approval=True`: este agente nunca decide por sí
    solo activar contramedidas, solo las recomienda.
    """

    name = "intrusion-agent"

    def relevant(self, incident: Incident) -> bool:
        return (incident.kind or "").upper() in ("INTRUSION","TAMPER","MOTION_BURST")

    def assess(self, incident: Incident) -> ActionProposal | None:
        kind = (incident.kind or "").upper()
        device = incident.details.get("device") or incident.details.get("trigger",{}).get("device_id")
        zone = incident.details.get("zone","")
        if kind == "TAMPER":
            return ActionProposal(
                agent_name=self.name, action_type="SOUND_ALARM", severity="CRITICAL",
                target_device_id=device, zone=zone,
                rationale="Manipulación física detectada en dispositivo (TAMPER); se recomienda sirena inmediata y notificación a autoridades.",
                payload={"escalate_to":"NOTIFY_AUTHORITIES","kind":kind}, requires_human_approval=True,
            )
        if kind == "INTRUSION":
            return ActionProposal(
                agent_name=self.name, action_type="LOCK_ACCESS", severity="CRITICAL",
                target_device_id=device, zone=zone,
                rationale="Secuencia DOOR+MOTION correlacionada como intrusión; se recomienda bloqueo de accesos de la zona.",
                payload={"kind":kind}, requires_human_approval=True,
            )
        if kind == "MOTION_BURST":
            return ActionProposal(
                agent_name=self.name, action_type="START_RECORDING", severity="MEDIUM",
                target_device_id=device, zone=zone,
                rationale="Ráfaga de movimiento sostenida; se inicia grabación de evidencia sin requerir aprobación (acción no destructiva).",
                payload={"kind":kind}, requires_human_approval=False,
            )
        return None
