from __future__ import annotations
import json
import logging
from typing import Any

log = logging.getLogger("command_journal")

BEGIN_OK = "OK"
BEGIN_DUPLICATE_COMMAND = "DUPLICATE_COMMAND"
BEGIN_REPLAYED_NONCE = "REPLAYED_NONCE"


class CommandJournal:
    """Durable command/audit journal. Physical execution is never recorded as
    successful until the adapter returns an accepted outcome.

    Garantías añadidas:
      * `begin` devuelve el resultado de la reserva (OK / DUPLICATE_COMMAND / REPLAYED_NONCE)
        en vez de ignorar en silencio un command_id repetido (antes se ejecutaba dos veces)
        o fallar con una excepción no controlada ante un nonce repetido.
      * El nonce es UNIQUE en la BD: el anti-replay sobrevive a reinicios del proceso.
      * `finish` solo transiciona RECEIVED -> estado final (idempotente, nunca pisa un resultado).
    """
    def __init__(self, pool):
        self.pool = pool

    async def ensure_schema(self):
        async with self.pool.acquire() as c:
            await c.execute('''
            CREATE TABLE IF NOT EXISTS equipment_command_journal (
              command_id UUID PRIMARY KEY,
              equipment_id TEXT NOT NULL,
              equipment_type TEXT NOT NULL,
              action TEXT NOT NULL,
              issued_by TEXT NOT NULL,
              nonce TEXT NOT NULL UNIQUE,
              issued_at DOUBLE PRECISION NOT NULL,
              expires_at DOUBLE PRECISION NOT NULL,
              status TEXT NOT NULL,
              reason TEXT,
              request JSONB NOT NULL,
              response JSONB,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              completed_at TIMESTAMPTZ
            );
            CREATE INDEX IF NOT EXISTS ix_equipment_command_journal_device_created
              ON equipment_command_journal(equipment_id, created_at DESC);
            ''')

    async def begin(self, command: Any) -> str:
        try:
            async with self.pool.acquire() as c:
                row = await c.fetchval('''
                  INSERT INTO equipment_command_journal
                  (command_id,equipment_id,equipment_type,action,issued_by,nonce,issued_at,expires_at,status,request)
                  VALUES($1,$2,$3,$4,$5,$6,$7,$8,'RECEIVED',$9::jsonb)
                  ON CONFLICT (command_id) DO NOTHING
                  RETURNING command_id
                ''', command.command_id, command.equipment_id, command.equipment_type.value,
                command.action, command.issued_by, command.nonce, command.issued_at,
                command.expires_at, json.dumps(command.parameters))
        except Exception as exc:  # noqa: BLE001
            if getattr(exc, "sqlstate", None) == "23505":  # unique_violation (nonce repetido)
                constraint = (getattr(exc, "constraint_name", "") or str(exc)).lower()
                return BEGIN_REPLAYED_NONCE if "nonce" in constraint else BEGIN_DUPLICATE_COMMAND
            raise
        return BEGIN_OK if row is not None else BEGIN_DUPLICATE_COMMAND

    async def finish(self, command_id: str, status: str, reason: str | None, response: dict | None = None):
        async with self.pool.acquire() as c:
            await c.execute('''
              UPDATE equipment_command_journal
              SET status=$2, reason=$3, response=$4::jsonb, completed_at=now()
              WHERE command_id=$1 AND status='RECEIVED'
            ''', command_id, status, reason, json.dumps(response) if response is not None else None)
