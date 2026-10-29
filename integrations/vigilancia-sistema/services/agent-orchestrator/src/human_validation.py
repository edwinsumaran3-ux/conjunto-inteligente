import time
from datetime import datetime, timedelta, timezone

# Ventanas de aprobación por severidad: cuanto más crítica la acción, menos
# tiempo se espera al operador antes de aplicar el fallback seguro.
APPROVAL_TIMEOUT_S = {"CRITICAL": 45, "HIGH": 90, "MEDIUM": 300, "LOW": 900}

class HumanValidationGate:
    """Encola acciones que requieren confirmación manual antes de ejecutarse.

    No ejecuta nada por sí misma: persiste la solicitud en
    `agent_approvals`, y `agent_loop.py` consulta periódicamente qué
    aprobaciones vencieron para aplicar el `fallback_action`
    preconfigurado (por defecto SAFE_HOLD, nunca la acción original).
    """

    def __init__(self, pool):
        self.pool = pool

    def timeout_for(self, severity: str) -> int:
        return APPROVAL_TIMEOUT_S.get(severity, 300)

    async def enqueue(self, action_id: str, severity: str, fallback_action: str = "SAFE_HOLD") -> dict:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.timeout_for(severity))
        async with self.pool.acquire() as c:
            row = await c.fetchrow(
                "INSERT INTO agent_approvals(action_id,expires_at,fallback_action) VALUES($1,$2,$3) RETURNING approval_id,expires_at",
                action_id, expires_at, fallback_action,
            )
        return {"approval_id": str(row["approval_id"]), "expires_at": row["expires_at"].isoformat()}

    async def decide(self, approval_id: str, decided_by: str, decision: str, signature: str | None) -> dict | None:
        async with self.pool.acquire() as c:
            row = await c.fetchrow(
                """UPDATE agent_approvals SET decision=$2,decided_by=$3,decided_at=now(),operator_signature=$4
                   WHERE approval_id=$1 AND decision='PENDING' AND expires_at>now() RETURNING approval_id,action_id,decision""",
                approval_id, decision, decided_by, signature,
            )
        if not row:
            return None
        async with self.pool.acquire() as c:
            await c.execute(
                "UPDATE agent_actions SET status=$2,resolved_at=now() WHERE action_id=$1",
                row["action_id"], "APPROVED" if decision == "APPROVED" else "REJECTED",
            )
        return dict(row)

    async def sweep_expired(self) -> list[dict]:
        """Vence las aprobaciones pendientes cuyo timeout pasó y devuelve
        la lista de acciones que deben ejecutar su fallback seguro."""
        async with self.pool.acquire() as c:
            rows = await c.fetch(
                "UPDATE agent_approvals SET decision='EXPIRED' WHERE decision='PENDING' AND expires_at<=now() RETURNING approval_id,action_id,fallback_action",
            )
            for r in rows:
                await c.execute("UPDATE agent_actions SET status='EXPIRED_FALLBACK',resolved_at=now() WHERE action_id=$1", r["action_id"])
        return [dict(r) for r in rows]

    async def pending(self) -> list[dict]:
        async with self.pool.acquire() as c:
            rows = await c.fetch(
                """SELECT a.approval_id,a.action_id,a.requested_at,a.expires_at,a.fallback_action,
                          x.agent_name,x.action_type,x.severity,x.target_device_id,x.zone,x.rationale,x.payload
                   FROM agent_approvals a JOIN agent_actions x ON x.action_id=a.action_id
                   WHERE a.decision='PENDING' ORDER BY a.requested_at ASC""",
            )
        return [dict(r) for r in rows]
