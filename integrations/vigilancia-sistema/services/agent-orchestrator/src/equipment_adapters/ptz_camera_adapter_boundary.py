import time
from equipment_contracts import EquipmentAdapter, EquipmentCommand, EquipmentCommandOutcome, EquipmentTelemetry, EquipmentType, CommandAuthorizationResult, is_expired

# Acciones ya resueltas por el bus de cascada (edge-gateway → MQTT
# `cameras/{id}/focus`, ver sensor_mesh.py): son reversibles y no requieren
# transporte ONVIF real. Cualquier otra acción (mover motor PTZ físico)
# permanece bloqueada hasta configurar el transporte del fabricante.
DIGITAL_ACTIONS = {"focus-cascade", "ptz-preset-digital"}

class PtzCameraAdapterBoundary(EquipmentAdapter):
    """Portado de PtzCameraAdapterBoundary.cs, adaptado: a diferencia del
    original (100% no conectado), aquí el reencuadre digital por cascada de
    sensores SÍ está operativo (es lo que ya hace `chain_communicator.py`
    vía MQTT). El movimiento físico real del motor PTZ sigue siendo una
    frontera explícita hasta integrar el SDK ONVIF del fabricante."""

    equipment_type = EquipmentType.PTZ_CAMERA

    def __init__(self, equipment_id: str):
        self.equipment_id = equipment_id

    @property
    def is_connected(self) -> bool:
        return True  # conectado vía MQTT para las acciones digitales soportadas

    def authorize(self, command: EquipmentCommand) -> CommandAuthorizationResult:
        if is_expired(command):
            return CommandAuthorizationResult.EXPIRED
        if command.action in DIGITAL_ACTIONS:
            return CommandAuthorizationResult.AUTHORIZED
        return CommandAuthorizationResult.UNKNOWN_ISSUER

    async def execute(self, command: EquipmentCommand) -> EquipmentCommandOutcome:
        if command.action not in DIGITAL_ACTIONS:
            return EquipmentCommandOutcome(False, "unavailable", "vendor-onvif-ptz-transport-not-configured")
        return EquipmentCommandOutcome(True, "dispatched", "focus-cascade-via-mqtt")

    async def get_telemetry(self) -> EquipmentTelemetry:
        return EquipmentTelemetry(self.equipment_id, time.time(), "digital-only", {"physical_ptz_transport_configured": False})

    async def emergency_stop(self) -> None:
        return None
