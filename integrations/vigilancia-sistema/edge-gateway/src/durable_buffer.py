"""Buffer persistente del edge-gateway (solo biblioteca estándar, probado de forma aislada).

Problemas del código anterior (`append_local`/`flush` en main.py) que resuelve:
  * PÉRDIDA DE EVENTOS: `flush` leía el archivo, esperaba al reenvío (await) y luego lo SOBRESCRIBÍA con los
    "restantes"; cualquier evento añadido durante esa espera desaparecía. Ahora el reemplazo conserva lo añadido.
  * Crecimiento sin límite del archivo y conteo O(n) de líneas en cada alta: ahora hay tope y contador en memoria.
  * Una línea corrupta se reintentaba para siempre: ahora se aparta a `<buffer>.corrupt`.
  * Eventos rechazados de forma permanente (HTTP 4xx) bloqueaban el reintento: se apartan a `<buffer>.rejected`.
  * Sin fsync: un corte de energía podía perder el último tramo.

Cuando se llega al tope se descartan primero los eventos de menor prioridad y más antiguos;
CRITICAL y SECURITY solo se descartan si TODO el buffer es de esa clase (se contabiliza en `dropped`).
"""
from __future__ import annotations

import json
import os
from typing import Any

PRIORITY_RANK = {"CRITICAL": 0, "SECURITY": 1, "ANOMALY": 2, "TELEMETRY": 3}


def _event_id(line: str) -> str | None:
    try:
        return json.loads(line).get("event_id")
    except Exception:  # noqa: BLE001
        return None


def _rank(line: str) -> int:
    try:
        return PRIORITY_RANK.get(json.loads(line).get("priority", "TELEMETRY"), 3)
    except Exception:  # noqa: BLE001
        return 3


class DurableBuffer:
    def __init__(self, path: str, max_events: int = 50_000):
        self.path = path
        self.max_events = max(1, max_events)
        self.dropped = 0
        self._count = 0
        self._ids: set[str] = set()
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                lines = [line for line in f if line.strip()]
            self._count = len(lines)
            self._ids = {i for i in map(_event_id, lines) if i}

    def __len__(self) -> int:
        return self._count

    def _fsync_append(self, target: str, text: str) -> None:
        with open(target, "a", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())

    def _read_lines(self) -> list[str]:
        if not os.path.exists(self.path):
            return []
        with open(self.path, encoding="utf-8") as f:
            return [ln.rstrip("\n") for ln in f if ln.strip()]

    def _atomic_write(self, lines: list[str]) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + ("\n" if lines else ""))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)
        self._count = len(lines)
        self._ids = {i for i in map(_event_id, lines) if i}

    def append(self, event: dict[str, Any]) -> bool:
        """Devuelve False si el evento ya estaba en el buffer: el firmware reenvía el mismo event_id hasta recibir
        ACK y antes cada reintento añadía una copia más."""
        eid = event.get("event_id")
        if eid and eid in self._ids:
            return False
        if self._count >= self.max_events:
            self._evict_one()
        self._fsync_append(self.path, json.dumps(event, separators=(",", ":")) + "\n")
        self._count += 1
        if eid:
            self._ids.add(eid)
        return True

    def _evict_one(self) -> None:
        lines = self._read_lines()
        if not lines:
            self._count = 0
            return
        worst = max(_rank(ln) for ln in lines)
        for i, ln in enumerate(lines):  # el más antiguo de la peor prioridad
            if _rank(ln) == worst:
                del lines[i]
                break
        self.dropped += 1
        self._atomic_write(lines)

    def snapshot(self) -> list[str]:
        """Líneas actuales (para reenviar sin retener el control del archivo)."""
        return self._read_lines()

    def commit_flush(self, snapshot: list[str], remaining: list[str], rejected: list[str] | None = None,
                     corrupt: list[str] | None = None) -> None:
        """Sustituye el contenido del snapshot por `remaining`, CONSERVANDO lo añadido mientras se reenviaba."""
        if rejected:
            self._fsync_append(self.path + ".rejected", "\n".join(rejected) + "\n")
        if corrupt:
            self._fsync_append(self.path + ".corrupt", "\n".join(corrupt) + "\n")
        current = self._read_lines()
        appended = current[len(snapshot):] if current[:len(snapshot)] == snapshot else [ln for ln in current if ln not in set(snapshot)]
        self._atomic_write(remaining + appended)
