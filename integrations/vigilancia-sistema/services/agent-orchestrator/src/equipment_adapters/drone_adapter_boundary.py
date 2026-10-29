from equipment_contracts import EquipmentAdapter, EquipmentCommand, EquipmentCommandOutcome, EquipmentTelemetry, EquipmentType, CommandAuthorizationResult, is_expired
from drone_catalog import DroneModel

class DroneAdapterBoundary(EquipmentAdapter):
    """Portado de DroneAdapterBoundary.cs. No habla con ningún SDK de
    fabricante: es la frontera explícita donde debe conectarse uno antes de
    uso en campo (ver docs/10-fusion-unificacion-plataforma.md). Mientras
    tanto rechaza en frío (fail-closed) cualquier ejecución real.

    `model` es opcional y solo aporta contexto informativo (fabricante,
    autonomía, si opera atado) tomado de `drone_catalog.py`; nunca habilita
    ejecución — el rechazo fail-closed es el mismo con o sin modelo asignado.
    """

    equipment_type = EquipmentType.DRONE

    def __init__(self, equipment_id: str, model: DroneModel | None = None):
        self.equipment_id = equipment_id
        self.model = model

    @property
    def is_connected(self) -> bool:
        return False

    def authorize(self, command: EquipmentCommand) -> CommandAuthorizationResult:
        if is_expired(command):
            return CommandAuthorizationResult.EXPIRED
        return CommandAuthorizationResult.UNKNOWN_ISSUER  # sin transporte del fabricante que valide la firma

    async def execute(self, command: EquipmentCommand) -> EquipmentCommandOutcome:
        return EquipmentCommandOutcome(False, "unavailable", "vendor-drone-transport-not-configured")

    async def get_telemetry(self) -> EquipmentTelemetry:
        import time
        values = {"transport_configured": False}
        if self.model:
            values.update({
                "vendor": self.model.vendor, "model": self.model.model, "category": self.model.category,
                "tethered": self.model.tethered, "max_flight_time_min": self.model.max_flight_time_min,
            })
        return EquipmentTelemetry(self.equipment_id, time.time(), "unavailable", values)

    async def emergency_stop(self) -> None:
        return None
