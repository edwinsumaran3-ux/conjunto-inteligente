import time
from equipment_contracts import EquipmentAdapter, EquipmentCommand, EquipmentCommandOutcome, EquipmentTelemetry, EquipmentType, CommandAuthorizationResult, is_expired

class IrActuatorAdapterBoundary(EquipmentAdapter):
    """Portado de IrDeterrentAdapterBoundary.cs. El sensor láser/IR de
    detección (tripwire, ver `laser_sensor.cpp` en el firmware) es de solo
    lectura y ya está operativo; este adaptador es distinto: representa un
    ACTUADOR IR (disuasor físico) que el orquestador podría accionar como
    contramedida. Hasta que exista verificación real de firma criptográfica
    end-to-end, se rechaza toda ejecución — el fail-safe físico del IR debe
    ser local al controlador de seguridad, nunca depender de este software
    central (misma corrección semántica que el hardening .NET)."""

    equipment_type = EquipmentType.IR_ACTUATOR

    def __init__(self, equipment_id: str):
        self.equipment_id = equipment_id

    @property
    def is_connected(self) -> bool:
        return True

    def authorize(self, command: EquipmentCommand) -> CommandAuthorizationResult:
        if is_expired(command):
            return CommandAuthorizationResult.EXPIRED
        # Frontera explícita: cualquier acción, reconocida o no, se rechaza
        # por falta de verificación criptográfica real conectada todavía.
        return CommandAuthorizationResult.UNKNOWN_ISSUER

    async def execute(self, command: EquipmentCommand) -> EquipmentCommandOutcome:
        return EquipmentCommandOutcome(False, "rejected", "signature-verification-required-before-ir-actuation")

    async def get_telemetry(self) -> EquipmentTelemetry:
        return EquipmentTelemetry(self.equipment_id, time.time(), "off", {"enabled": False})

    async def emergency_stop(self) -> None:
        return None
