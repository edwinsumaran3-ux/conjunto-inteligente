"""Orquesta BD <-> dominio SST. Todas las consultas son por tenant (además de RLS FORCE).
Estado: COMPILA; NO ejecutado contra PostgreSQL (ver MODULE_CONTRACT.md)."""
from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.audit import append_audit_event
from backend.app.platform.security.strong_auth import verify_totp_credential
from ..domain import approvals as AP
from ..domain import audit_chain as CH
from ..domain import coverage as CV
from ..domain import work_permit as WP
from ..domain.authority import resolve as resolve_authority
from ..domain.rules_engine import ActivityContext, Evaluation, NoApplicableRules, RulesEngine

_J = lambda v: json.dumps(v, default=str, separators=(",", ":"))  # noqa: E731
now_utc = lambda: datetime.now(timezone.utc)  # noqa: E731


class NotFound(LookupError):
    pass


class SstService:
    # ---------------- auditoría: audit_log existente + cadena de hash por tenant ----------------
    async def audit(self, s: AsyncSession, tenant: UUID, actor: UUID | None, action: str, entity_type: str,
                    entity_id: str, *, before=None, after=None, result: str = "ok", rule_applied: str | None = None,
                    correlation_id: str | None = None) -> None:
        before = json.loads(_J(before)) if before is not None else None
        after = json.loads(_J(after)) if after is not None else None
        await append_audit_event(s, tenant_id=tenant, actor_id=actor, action=action, entity_type=entity_type,
                                 entity_id=entity_id, before=before, after=after)
        # Serializa por tenant: evita que dos escrituras concurrentes bifurquen la cadena.
        await s.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": f"sst-chain:{tenant}"})
        row = (await s.execute(text("SELECT seq,prev_hash,hash,created_at_iso,event FROM sst_audit_chain "
                                    "WHERE tenant_id=:t ORDER BY seq DESC LIMIT 1"), {"t": tenant})).mappings().first()
        last = CH.ChainLink(row["seq"], row["prev_hash"], row["hash"], row["created_at_iso"], row["event"]) if row else None
        ev = {"tenant_id": str(tenant), "actor_id": str(actor) if actor else None, "action": action,
              "entity_type": entity_type, "entity_id": entity_id, "before": before, "after": after,
              "rule_applied": rule_applied, "document_version": None, "result": result,
              "correlation_id": correlation_id or str(uuid4())}
        ev = json.loads(_J(ev))  # normaliza tipos exactamente como se persistirán
        link = CH.next_link(last, now_utc().isoformat(), ev)  # UNA sola marca de tiempo
        await s.execute(text("INSERT INTO sst_audit_chain(tenant_id,seq,prev_hash,hash,created_at_iso,event) "
                             "VALUES (:t,:q,:p,:h,:c,CAST(:e AS jsonb))"),
                        {"t": tenant, "q": link.seq, "p": link.prev_hash, "h": link.hash, "c": link.created_at_iso, "e": _J(ev)})

    async def verify_audit_chain(self, s: AsyncSession, tenant: UUID) -> CH.ChainVerdict:
        rows = (await s.execute(text("SELECT seq,prev_hash,hash,created_at_iso,event FROM sst_audit_chain "
                                     "WHERE tenant_id=:t ORDER BY seq"), {"t": tenant})).mappings().all()
        return CH.verify([CH.ChainLink(r["seq"], r["prev_hash"], r["hash"], r["created_at_iso"], r["event"]) for r in rows])

    # ---------------- actividades y evaluación ----------------
    async def create_activity(self, s, tenant: UUID, actor: UUID, d: dict) -> UUID:
        aid = (await s.execute(text("""INSERT INTO sst_activities(tenant_id,zone_id,activity_type,jurisdiction,risk_level,
            start_at,end_at,aforo,contractor_id,asset_id,requester_id,timezone)
            VALUES (:t,:zone,:type,:jur,:risk,:s0,:s1,:aforo,:con,:asset,:req,:tz) RETURNING id"""),
            {"t": tenant, "zone": d["zone_id"], "type": d["activity_type"], "jur": d["jurisdiction"], "risk": d["risk_level"],
             "s0": d["start_at"], "s1": d["end_at"], "aforo": d.get("aforo"), "con": d.get("contractor_id"),
             "asset": d.get("asset_id"), "req": actor, "tz": d.get("timezone", "America/Bogota")})).scalar_one()
        await self.audit(s, tenant, actor, "sst.activity.created", "SstActivity", str(aid), after=d)
        return aid

    async def _activity(self, s, tenant: UUID, activity_id: UUID):
        r = (await s.execute(text("SELECT * FROM sst_activities WHERE tenant_id=:t AND id=:i FOR UPDATE"),
                             {"t": tenant, "i": activity_id})).mappings().first()
        if not r:
            raise NotFound("actividad")
        return r

    async def evaluate(self, s: AsyncSession, tenant: UUID, actor: UUID, activity_id: UUID) -> Evaluation | None:
        a = await self._activity(s, tenant, activity_id)
        ctx = ActivityContext(str(a["id"]), a["activity_type"], a["jurisdiction"], a["risk_level"], str(a["zone_id"]),
                              a["start_at"], a["end_at"], a["timezone"], a["aforo"],
                              str(a["contractor_id"]) if a["contractor_id"] else None,
                              str(a["asset_id"]) if a["asset_id"] else None, str(a["requester_id"]))
        rules = [dict(r) | {"id": str(r["id"]), "approved_by": str(r["approved_by"])} for r in (await s.execute(text(
            "SELECT * FROM sst_rules WHERE tenant_id=:t AND jurisdiction=:j AND activity_type=:a"),
            {"t": tenant, "j": a["jurisdiction"], "a": a["activity_type"]})).mappings().all()]
        ev = [dict(r) | {"id": str(r["id"]), "type": r["evidence_type"],
                         "scope_id": str(r["scope_id"]) if r["scope_id"] else None,
                         "uploaded_by": str(r["uploaded_by"]), "reviewed_by": str(r["reviewed_by"]) if r["reviewed_by"] else None}
              for r in (await s.execute(text("SELECT * FROM sst_evidence WHERE tenant_id=:t"), {"t": tenant})).mappings().all()]
        exc = [dict(r) | {"approval_id": str(r["approval_id"]), "approved_by": str(r["approved_by"])} for r in (await s.execute(
            text("SELECT * FROM sst_exceptions WHERE tenant_id=:t AND activity_id=:i"), {"t": tenant, "i": activity_id})).mappings().all()]
        try:
            res = RulesEngine().evaluate(ctx, rules, ev, exc)
        except NoApplicableRules:
            await s.execute(text("UPDATE sst_activities SET status='blocked',updated_at=now() WHERE id=:i"), {"i": activity_id})
            await self.audit(s, tenant, actor, "sst.evaluate.no_rules", "SstActivity", str(activity_id), result="desconocido")
            raise
        for r in res.results:
            await s.execute(text("""INSERT INTO sst_requirement_evaluations(tenant_id,activity_id,requirement_key,rule_id,
                rule_version,status,severity,mandatory,reason,evidence_id) VALUES (:t,:a,:k,:rid,:rv,:st,:sv,:m,:why,:ev)
                ON CONFLICT (tenant_id,activity_id,requirement_key) DO UPDATE SET rule_id=EXCLUDED.rule_id,
                rule_version=EXCLUDED.rule_version,status=EXCLUDED.status,severity=EXCLUDED.severity,
                mandatory=EXCLUDED.mandatory,reason=EXCLUDED.reason,evidence_id=EXCLUDED.evidence_id,evaluated_at=now()"""),
                {"t": tenant, "a": activity_id, "k": r.requirement_key, "rid": r.rule_id, "rv": r.rule_version,
                 "st": r.status.value, "sv": r.severity.value, "m": r.mandatory, "why": r.reason, "ev": r.evidence_id})
        new = "blocked" if res.blocked else "evaluating"
        await s.execute(text("UPDATE sst_activities SET status=:s,updated_at=now() WHERE id=:i"), {"s": new, "i": activity_id})
        await self.audit(s, tenant, actor, "sst.evaluate.completed", "SstActivity", str(activity_id),
                         after={"counts": res.counts(), "blockers": [b.requirement_key for b in res.blockers]},
                         result="blocked" if res.blocked else "ok", rule_applied=",".join(f"{k}@{v}" for k, v in res.rules_used))
        return res

    async def requirements(self, s, tenant: UUID, activity_id: UUID) -> list[dict]:
        return [dict(r) for r in (await s.execute(text(
            "SELECT requirement_key,status,severity,mandatory,reason,rule_version,evidence_id,evaluated_at "
            "FROM sst_requirement_evaluations WHERE tenant_id=:t AND activity_id=:a ORDER BY requirement_key"),
            {"t": tenant, "a": activity_id})).mappings().all()]

    async def _is_blocked(self, s, tenant: UUID, activity_id: UUID) -> bool:
        """Fail-closed: bloqueada si hay obligatorios sin cumplir O si nunca fue evaluada."""
        n = (await s.execute(text("SELECT count(*) AS total, count(*) FILTER (WHERE mandatory AND status NOT IN "
                                  "('cumple','no_aplica','excepcion')) AS bad FROM sst_requirement_evaluations "
                                  "WHERE tenant_id=:t AND activity_id=:a"), {"t": tenant, "a": activity_id})).mappings().one()
        return n["total"] == 0 or n["bad"] > 0

    # ---------------- aprobaciones ----------------
    async def create_approval(self, s, tenant: UUID, requester: UUID, d: dict) -> tuple[UUID, dict[str, str]]:
        m = (await s.execute(text("SELECT matrix FROM sst_authority_matrix WHERE tenant_id=:t ORDER BY version DESC LIMIT 1"),
                             {"t": tenant})).scalar_one_or_none()
        users = [{"id": str(r["id"]), "roles": [r["role"]], "active": r["is_active"]} for r in (await s.execute(text(
            "SELECT u.id,u.is_active,r.name AS role FROM users u JOIN user_roles ur ON ur.user_id=u.id "
            "JOIN roles r ON r.id=ur.role_id WHERE u.tenant_id=:t"), {"t": tenant})).mappings().all()]
        merged: dict[str, dict] = {}
        for u in users:
            merged.setdefault(u["id"], {"id": u["id"], "roles": [], "active": u["active"]})["roles"] += u["roles"]
        res = resolve_authority(m, request_type=d["request_type"], risk_level=d["risk_level"], requester_id=str(requester),
                                users=list(merged.values()), amount=d.get("amount"))
        ttl = int(d.get("ttl_hours", 24))
        if not 1 <= ttl <= 168:
            raise AP.ApprovalError("TTL_OUT_OF_RANGE")
        exp = now_utc() + timedelta(hours=ttl)
        apid = (await s.execute(text("""INSERT INTO sst_approvals(tenant_id,activity_id,request_type,action,risk_level,requester_id,
            primary_id,backup_id,approver_role,requires_mfa,expires_at,conditions) VALUES (:t,:act,:rt,:ac,:rk,:rq,:p,:b,:role,:mfa,:e,
            CAST(:c AS jsonb)) RETURNING id"""), {"t": tenant, "act": d.get("activity_id"), "rt": d["request_type"], "ac": d["action"],
            "rk": d["risk_level"], "rq": requester, "p": res.primary_id, "b": res.backup_id, "role": res.approver_role,
            "mfa": res.requires_mfa, "e": exp, "c": _J(d.get("conditions", {}))})).scalar_one()
        domain = AP.Approval(str(apid), d.get("activity_id"), d["action"], str(requester), res.primary_id, res.backup_id,
                             res.requires_mfa, exp)
        raw, rec = AP.issue_token(domain, res.primary_id, now_utc())
        await s.execute(text("""INSERT INTO sst_approval_tokens(tenant_id,approval_id,token_hash,recipient_id,action,version,expires_at)
            VALUES (:t,:a,:h,:r,:ac,:v,:e)"""), {"t": tenant, "a": apid, "h": rec.token_hash, "r": res.primary_id,
                                               "ac": rec.action, "v": rec.version, "e": rec.expires_at})
        await self.audit(s, tenant, requester, "sst.approval.created", "SstApproval", str(apid),
                         after={"primary": res.primary_id, "backup": res.backup_id, "mfa": res.requires_mfa, "reason": res.reason})
        # El token en claro SOLO se entrega al canal de notificación; nunca se persiste ni se registra.
        return apid, {"token": raw, "recipient_id": res.primary_id}

    async def decide(self, s, tenant: UUID, actor: UUID, approval_id: UUID, *, token: str, decision: str,
                     justification: str | None, mfa_code: str | None) -> str:
        r = (await s.execute(text("SELECT * FROM sst_approvals WHERE tenant_id=:t AND id=:i FOR UPDATE"),
                             {"t": tenant, "i": approval_id})).mappings().first()
        if not r:
            raise NotFound("aprobación")
        ap = AP.Approval(str(r["id"]), str(r["activity_id"]) if r["activity_id"] else None, r["action"], str(r["requester_id"]),
                         str(r["primary_id"]), str(r["backup_id"]) if r["backup_id"] else None, r["requires_mfa"],
                         r["expires_at"], r["version"], AP.ApprovalStatus(r["status"]))
        t0 = now_utc()
        if (exp := AP.expire_if_due(ap, t0)).status is AP.ApprovalStatus.EXPIRED and ap.status is AP.ApprovalStatus.PENDING:
            await s.execute(text("UPDATE sst_approvals SET status='expired' WHERE id=:i"), {"i": approval_id})
            await self.audit(s, tenant, actor, "sst.approval.expired", "SstApproval", str(approval_id), result="expired")
            raise AP.ApprovalError("APPROVAL_EXPIRED")
        mfa_ok = bool(mfa_code) and await verify_totp_credential(s, tenant_id=tenant, actor_id=actor, code=mfa_code)
        tr = (await s.execute(text("SELECT * FROM sst_approval_tokens WHERE tenant_id=:t AND token_hash=:h"),
                              {"t": tenant, "h": AP.hash_token(token)})).mappings().first()
        rec = AP.TokenRecord(tr["token_hash"], str(tr["approval_id"]), str(tr["recipient_id"]), tr["action"], tr["version"],
                             tr["expires_at"], tr["used_at"], tr["revoked"]) if tr else None
        try:
            AP.validate_token(rec, token, approval=ap, action=r["action"], actor_id=str(actor), now=t0, mfa_verified=mfa_ok)
            new = AP.decide(ap, actor_id=str(actor), decision=decision, justification=justification, now=t0, mfa_verified=mfa_ok)
        except AP.ApprovalError as e:
            await self.audit(s, tenant, actor, "sst.approval.rejected_attempt", "SstApproval", str(approval_id), result=e.code)
            raise
        # Consumo atómico: solo uno gana si hay concurrencia o replay.
        used = await s.execute(text("UPDATE sst_approval_tokens SET used_at=now() WHERE tenant_id=:t AND token_hash=:h "
                                    "AND used_at IS NULL AND revoked=false RETURNING id"), {"t": tenant, "h": rec.token_hash})
        if used.first() is None:
            raise AP.ApprovalError("TOKEN_REPLAY")
        await s.execute(text("UPDATE sst_approvals SET status=:st,decided_by=:u,decided_at=now(),justification=:j WHERE id=:i"),
                        {"st": new.status.value, "u": actor, "j": justification, "i": approval_id})
        await self.audit(s, tenant, actor, f"sst.approval.{new.status.value}", "SstApproval", str(approval_id),
                         after={"decision": decision, "justification": justification, "mfa": mfa_ok})
        return new.status.value

    async def expire_due(self, s, tenant: UUID) -> int:
        """Worker idempotente: vence aprobaciones sin decisión. NUNCA aprueba; la actividad sigue bloqueada."""
        rows = (await s.execute(text("UPDATE sst_approvals SET status='expired' WHERE tenant_id=:t AND status='pending' "
                                     "AND expires_at<=now() RETURNING id,activity_id"), {"t": tenant})).mappings().all()
        for r in rows:
            await self.audit(s, tenant, None, "sst.approval.expired", "SstApproval", str(r["id"]), result="expired",
                             after={"note": "expirada sin decisión; no equivale a aprobación"})
            if r["activity_id"]:
                await s.execute(text("UPDATE sst_activities SET status='blocked' WHERE id=:i AND status IN ('approved','evaluating')"),
                                {"i": r["activity_id"]})
        return len(rows)

    # ---------------- permisos de trabajo ----------------
    async def activate_permit(self, s, tenant: UUID, actor: UUID, permit_id: UUID) -> str:
        p = (await s.execute(text("SELECT * FROM sst_work_permits WHERE tenant_id=:t AND id=:i FOR UPDATE"),
                             {"t": tenant, "i": permit_id})).mappings().first()
        if not p:
            raise NotFound("permiso")
        ats = (await s.execute(text("SELECT * FROM sst_ats WHERE tenant_id=:t AND id=:i"), {"t": tenant, "i": p["ats_id"]})).mappings().one()
        granted = False
        if p["approval_id"]:
            granted = (await s.execute(text("SELECT status='approved' AND activity_id=:act FROM sst_approvals "
                                            "WHERE tenant_id=:t AND id=:i"),
                                       {"t": tenant, "i": p["approval_id"], "act": p["activity_id"]})).scalar_one_or_none() is True
        wp = WP.WorkPermit(str(p["id"]), str(p["activity_id"]), str(p["ats_id"]), p["ats_version"], p["permit_type"], str(p["zone_id"]),
                           str(p["contractor_id"]), frozenset(p["worker_ids"]), p["valid_from"], p["valid_to"])
        missing = WP.validate_ats(ats["steps"], ats["signatures"], ats["required_signers"])
        out = WP.activate(wp, now=now_utc(), approval_granted=granted,
                          evaluation_blocked=await self._is_blocked(s, tenant, p["activity_id"]), ats_missing=missing)
        await s.execute(text("UPDATE sst_work_permits SET status=:st WHERE id=:i"), {"st": out.status.value, "i": permit_id})
        await self.audit(s, tenant, actor, "sst.permit.activated", "SstWorkPermit", str(permit_id), after={"valid_to": p["valid_to"]})
        return out.status.value

    # ---------------- cobertura y asignación temporal ----------------
    async def coverage(self, s, tenant: UUID, activity_id: UUID, asset_type: str, required_units: float | None) -> CV.CoverageResult:
        a = await self._activity(s, tenant, activity_id)
        assets = [dict(r) | {"id": str(r["id"]), "zone_id": str(r["zone_id"]),
                             "capacity_units": float(r["capacity_units"]) if r["capacity_units"] is not None else None}
                  for r in (await s.execute(text("SELECT * FROM sst_asset_registry WHERE tenant_id=:t AND asset_type=:y"),
                                            {"t": tenant, "y": asset_type})).mappings().all()]
        asg = [dict(r) | {"asset_id": str(r["asset_id"]), "zone_id": str(r["zone_id"])} for r in (await s.execute(text(
            "SELECT * FROM sst_temporary_assignments WHERE tenant_id=:t AND zone_id=:z AND status IN ('verified','active')"),
            {"t": tenant, "z": a["zone_id"]})).mappings().all()]
        other = [{"asset_id": str(r["asset_id"]), "activity_zone": str(r["zone_id"]), "start_at": r["start_at"], "end_at": r["end_at"]}
                 for r in (await s.execute(text("SELECT asset_id,zone_id,start_at,end_at FROM sst_temporary_assignments WHERE "
                                                "tenant_id=:t AND status IN ('verified','active')"), {"t": tenant})).mappings().all()]
        return CV.compute_coverage(zone_id=str(a["zone_id"]), asset_type=asset_type, required_units=required_units,
                                   start_at=a["start_at"], end_at=a["end_at"], assets=assets, assignments=asg, other_reservations=other)

    async def propose_assignment(self, s, tenant: UUID, actor: UUID, d: dict) -> UUID:
        CV.propose(id="new", activity_id=str(d["activity_id"]), asset_id=str(d["asset_id"]), zone_id=str(d["zone_id"]),
                   start_at=d["start_at"], end_at=d["end_at"], responsible_id=str(d["responsible_id"]), proposed_by=str(actor))
        i = (await s.execute(text("""INSERT INTO sst_temporary_assignments(tenant_id,activity_id,asset_id,zone_id,start_at,end_at,
            responsible_id,proposed_by) VALUES (:t,:a,:as,:z,:s0,:s1,:r,:p) RETURNING id"""), {"t": tenant, "a": d["activity_id"],
            "as": d["asset_id"], "z": d["zone_id"], "s0": d["start_at"], "s1": d["end_at"], "r": d["responsible_id"], "p": actor})).scalar_one()
        await self.audit(s, tenant, actor, "sst.assignment.proposed", "SstTemporaryAssignment", str(i), after=d)
        return i

    async def verify_assignment(self, s, tenant: UUID, actor: UUID, assignment_id: UUID, inspection_id: UUID | None, ok: bool) -> str:
        r = (await s.execute(text("SELECT * FROM sst_temporary_assignments WHERE tenant_id=:t AND id=:i FOR UPDATE"),
                             {"t": tenant, "i": assignment_id})).mappings().first()
        if not r:
            raise NotFound("asignación")
        a = CV.TemporaryAssignment(str(r["id"]), str(r["activity_id"]), str(r["asset_id"]), str(r["zone_id"]), r["start_at"], r["end_at"],
                                   str(r["responsible_id"]), str(r["proposed_by"]), r["status"])
        v = CV.verify(a, verifier_id=str(actor), inspection_id=str(inspection_id) if inspection_id else None, physical_check_ok=ok)
        await s.execute(text("UPDATE sst_temporary_assignments SET status='verified',inspection_id=:n,verified_by=:u WHERE id=:i"),
                        {"n": inspection_id, "u": actor, "i": assignment_id})
        await self.audit(s, tenant, actor, "sst.assignment.verified", "SstTemporaryAssignment", str(assignment_id))
        return v.status
