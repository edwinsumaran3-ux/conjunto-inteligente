import logging
import time

from equipment_contracts import EquipmentAdapter, EquipmentCommand, EquipmentCommandOutcome, CommandAuthorizationResult, is_expired
from control.command_security import verify_command

log = logging.getLogger("equipment_registry")

NONCE_RETENTION_S = 15 * 60
# Ventana máxima de vigencia de un comando y tolerancia de reloj hacia el futuro.
MAX_COMMAND_TTL_S = 300
MAX_CLOCK_SKEW_S = 30


class EquipmentRegistry:
    """Portado de EquipmentRegistry.cs. Mantiene los adaptadores admitidos y
    es el único camino para ejecutar un comando sobre hardware físico:
    valida ventana de vigencia, rechaza nonces repetidos (replay) y exige
    `authorize` antes de `execute`. `ChainCommunicator` despacha aquí en
    vez de hablar directo con un adaptador.

    Endurecimiento:
      * Si hay journal y NO está disponible, el comando se rechaza (`journal-unavailable`):
        no se actúa sobre hardware sin evidencia durable.
      * Todo rechazo (también los tempranos) cierra la fila del journal; antes quedaban en RECEIVED.
      * command_id y nonce repetidos se rechazan también tras un reinicio (la BD es la autoridad).
      * Excepciones de `authorize`/`execute` se contienen y se registran como resultado, sin 500.
    """

    def __init__(self, journal=None, audit=None):
        self._journal = journal
        self._audit = audit
        self._adapters: dict[str, EquipmentAdapter] = {}
        self._seen_nonces: dict[str, float] = {}

    def register(self, adapter: EquipmentAdapter):
        self._adapters[adapter.equipment_id] = adapter

    def all(self) -> list[EquipmentAdapter]:
        return list(self._adapters.values())

    def _prune_nonces(self):
        cutoff = time.time() - NONCE_RETENTION_S
        for nonce, seen_at in list(self._seen_nonces.items()):
            if seen_at < cutoff:
                del self._seen_nonces[nonce]

    async def _close(self, command: EquipmentCommand, outcome: EquipmentCommandOutcome, response: dict | None = None):
        if self._journal:
            try:
                await self._journal.finish(command.command_id, outcome.status, outcome.reason, response)
            except Exception:  # noqa: BLE001
                log.exception("no se pudo cerrar el journal del comando %s", command.command_id)
        if self._audit:
            await self._audit.record(
                actor=command.issued_by, actor_type="AGENT", action=f"EQUIPMENT_COMMAND_{outcome.status.upper()}",
                entity_type="equipment", entity_id=command.equipment_id,
                details={"command_id": command.command_id, "action": command.action, "reason": outcome.reason},
            )

    async def _reject(self, command: EquipmentCommand, reason: str) -> EquipmentCommandOutcome:
        outcome = EquipmentCommandOutcome(False, "rejected", reason)
        await self._close(command, outcome)
        return outcome

    async def dispatch(self, command: EquipmentCommand) -> EquipmentCommandOutcome:
        self._prune_nonces()
        if self._journal:
            try:
                begun = await self._journal.begin(command)
            except Exception:  # noqa: BLE001
                log.exception("journal no disponible: comando %s rechazado (fail-closed)", command.command_id)
                return EquipmentCommandOutcome(False, "rejected", "journal-unavailable")
            if begun != "OK":
                # Fila ajena ya existente (mismo command_id o nonce): no se cierra, pertenece a otro comando.
                return EquipmentCommandOutcome(False, "rejected", begun.lower().replace("_", "-"))
        adapter = self._adapters.get(command.equipment_id)
        if adapter is None:
            return await self._reject(command, "unknown-equipment")
        if adapter.equipment_type != command.equipment_type:
            return await self._reject(command, "equipment-type-mismatch")
        if is_expired(command):
            return await self._reject(command, "invalid-command-window")
        if command.nonce in self._seen_nonces:
            return await self._reject(command, "replayed-nonce")
        if command.signature in {"", "system-issued:unverified", "unverified"}:
            return await self._reject(command, "missing-verified-signature")
        if not verify_command(command):
            return await self._reject(command, "invalid-command-signature")
        # Ventana estricta: solo tras verificar firma (un atacante sin clave no llega aquí).
        now = time.time()
        if command.expires_at - command.issued_at > MAX_COMMAND_TTL_S or command.issued_at > now + MAX_CLOCK_SKEW_S:
            return await self._reject(command, "invalid-command-window")
        self._seen_nonces[command.nonce] = time.time()
        try:
            auth = adapter.authorize(command)
        except Exception:  # noqa: BLE001
            log.exception("authorize lanzó excepción (%s)", command.equipment_id)
            return await self._reject(command, "authorize-error")
        if auth != CommandAuthorizationResult.AUTHORIZED:
            return await self._reject(command, auth.value)
        try:
            outcome = await adapter.execute(command)
        except Exception as exc:  # noqa: BLE001
            log.exception("execute lanzó excepción (%s)", command.equipment_id)
            outcome = EquipmentCommandOutcome(False, "error", f"adapter-exception:{type(exc).__name__}")
        await self._close(command, outcome, {"accepted": outcome.accepted})
        return outcome

    async def emergency_stop_all(self) -> dict[str, str]:
        """Intenta detener TODO equipo; un fallo en uno no impide detener los demás.
        Devuelve {equipment_id: 'ok' | 'error:<Clase>'} para que el operador vea qué no confirmó."""
        results: dict[str, str] = {}
        for adapter in self._adapters.values():
            try:
                await adapter.emergency_stop()
                results[adapter.equipment_id] = "ok"
            except Exception as exc:  # noqa: BLE001
                log.exception("emergency_stop falló en %s", adapter.equipment_id)
                results[adapter.equipment_id] = f"error:{type(exc).__name__}"
        if self._audit:
            await self._audit.record(actor="operator", actor_type="OPERATOR", action="EMERGENCY_STOP_ALL",
                                     entity_type="equipment", details={"results": results})
        return results
