import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EquipmentType(str, Enum):
    DRONE = "DRONE"
    PTZ_CAMERA = "PTZ_CAMERA"
    GROUND_ROBOT = "GROUND_ROBOT"
    IR_ACTUATOR = "IR_ACTUATOR"


class CommandAuthorizationResult(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    EXPIRED = "EXPIRED"
    REPLAYED_NONCE = "REPLAYED_NONCE"
    UNKNOWN_ISSUER = "UNKNOWN_ISSUER"


@dataclass(frozen=True)
class EquipmentCommand:
    """Envoltorio de comando hacia un equipo físico (dron, PTZ, robot, IR).

    Portado de `EquipmentCommand` en IEquipmentAdapter.cs. `nonce` es de un
    solo uso (ver `EquipmentRegistry`), `expires_at` acota la ventana de
    validez, y `signature` debe verificarse antes de cualquier I/O real —
    ningún adaptador puede saltarse `Authorize`.
    """

    command_id: str
    nonce: str
    equipment_type: EquipmentType
    equipment_id: str
    action: str
    parameters: dict[str, Any]
    issued_at: float
    expires_at: float
    issued_by: str
    signature: str


@dataclass(frozen=True)
class EquipmentTelemetry:
    equipment_id: str
    timestamp: float
    state: str
    values: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EquipmentCommandOutcome:
    accepted: bool
    status: str
    reason: str | None = None


class EquipmentAdapter(ABC):
    """Contrato que debe implementar todo equipo físico admitido en la
    plataforma (dron, cámara PTZ, robot terrestre, actuador IR).

    Portado de IEquipmentAdapter.cs: este es el único punto de paso para
    ejecutar un comando. Ningún adaptador puede ejecutar sin pasar antes
    por `authorize`, y todo adaptador debe exponer un `emergency_stop`
    independiente del resto del software (estado seguro por hardware).
    """

    equipment_id: str
    equipment_type: EquipmentType

    @property
    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    def authorize(self, command: EquipmentCommand) -> CommandAuthorizationResult: ...

    @abstractmethod
    async def execute(self, command: EquipmentCommand) -> EquipmentCommandOutcome: ...

    @abstractmethod
    async def get_telemetry(self) -> EquipmentTelemetry: ...

    @abstractmethod
    async def emergency_stop(self) -> None: ...


def is_expired(command: EquipmentCommand) -> bool:
    return time.time() > command.expires_at or command.issued_at > command.expires_at
