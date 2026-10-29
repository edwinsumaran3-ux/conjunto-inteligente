from agents.base_agent import BaseAgent
from models import Incident, ActionProposal

class HardwareIntegrityAgent(BaseAgent):
    """Especializado en salud de hardware: cámaras degradadas/offline y
    sensores con heartbeat perdido. Nunca propone acciones destructivas;
    su única acción con aprobación humana es NOTIFY_AUTHORITIES cuando la
    pérdida de hardware es total en una zona (posible sabotaje coordinado).
    """

    name = "hardware-integrity-agent"

    def relevant(self, incident: Incident) -> bool:
        return (incident.kind or "").upper() in ("DEVICE_TAMPERING","CAMERA_FAILOVER","HEARTBEAT_LOST")

    def assess(self, incident: Incident) -> ActionProposal | None:
        kind = (incident.kind or "").upper()
        device = incident.details.get("device") or incident.details.get("device_id")
        zone = incident.details.get("zone","")
        if kind == "DEVICE_TAMPERING":
            return ActionProposal(
                agent_name=self.name, action_type="NOTIFY_AUTHORITIES", severity="CRITICAL",
                target_device_id=device, zone=zone,
                rationale="Patrón combinado de TAMPER+CAMERA_OFFLINE+SENSOR_FAIL clasificado como sabotaje de hardware.",
                payload={"kind":kind}, requires_human_approval=True,
            )
        return ActionProposal(
            agent_name=self.name, action_type="SAFE_HOLD", severity="MEDIUM",
            target_device_id=device, zone=zone,
            rationale=f"Degradación de hardware ({kind}) sin evidencia de sabotaje; se mantiene modo seguro y monitoreo reforzado.",
            payload={"kind":kind}, requires_human_approval=False,
        )
