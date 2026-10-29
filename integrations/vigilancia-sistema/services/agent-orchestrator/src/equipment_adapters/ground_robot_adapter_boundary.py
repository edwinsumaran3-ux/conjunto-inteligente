import time
from equipment_contracts import EquipmentAdapter, EquipmentCommand, EquipmentCommandOutcome, EquipmentTelemetry, EquipmentType, CommandAuthorizationResult, is_expired

class GroundRobotAdapterBoundary(EquipmentAdapter):
    """Portado de GroundRobotAdapterBoundary.cs. Frontera explícita para un
    robot terrestre de patrullaje; requiere el protocolo del fabricante
    antes de aceptar comandos de navegación reales."""

    equipment_type = EquipmentType.GROUND_ROBOT

    def __init__(self, equipment_id: str):
        self.equipment_id = equipment_id

    @property
    def is_connected(self) -> bool:
        return False

    def authorize(self, command: EquipmentCommand) -> CommandAuthorizationResult:
        if is_expired(command):
            return CommandAuthorizationResult.EXPIRED
        return CommandAuthorizationResult.UNKNOWN_ISSUER

    async def execute(self, command: EquipmentCommand) -> EquipmentCommandOutcome:
        return EquipmentCommandOutcome(False, "unavailable", "vendor-ground-robot-transport-not-configured")

    async def get_telemetry(self) -> EquipmentTelemetry:
        return EquipmentTelemetry(self.equipment_id, time.time(), "unavailable", {"transport_configured": False})

    async def emergency_stop(self) -> None:
        return None
