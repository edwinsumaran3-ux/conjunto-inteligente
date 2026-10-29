"""Cadena de hash de auditoría (spec §12). Una sola marca de tiempo; JSON canónico; verificable."""
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

GENESIS = "GENESIS"
FIELDS = ("tenant_id", "actor_id", "action", "entity_type", "entity_id", "before", "after",
          "rule_applied", "document_version", "result", "correlation_id")


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def compute_hash(prev_hash: str, seq: int, created_at_iso: str, event: Mapping[str, Any]) -> str:
    body = {k: event.get(k) for k in FIELDS}
    return hashlib.sha256(canonical({"prev": prev_hash, "seq": seq, "ts": created_at_iso, "event": body}).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ChainLink:
    seq: int
    prev_hash: str
    hash: str
    created_at_iso: str
    event: Mapping[str, Any]


def next_link(last: ChainLink | None, created_at_iso: str, event: Mapping[str, Any]) -> ChainLink:
    seq = 1 if last is None else last.seq + 1
    prev = GENESIS if last is None else last.hash
    return ChainLink(seq, prev, compute_hash(prev, seq, created_at_iso, event), created_at_iso, event)


@dataclass(frozen=True, slots=True)
class ChainVerdict:
    valid: bool
    checked: int
    first_bad_seq: int | None = None
    reason: str | None = None


def verify(links: Sequence[ChainLink]) -> ChainVerdict:
    prev, expect = GENESIS, 1
    for l in links:
        if l.seq != expect:
            return ChainVerdict(False, expect - 1, l.seq, "hueco o duplicado en la secuencia")
        if l.prev_hash != prev:
            return ChainVerdict(False, expect - 1, l.seq, "prev_hash no coincide (cadena bifurcada o alterada)")
        if compute_hash(l.prev_hash, l.seq, l.created_at_iso, l.event) != l.hash:
            return ChainVerdict(False, expect - 1, l.seq, "hash no coincide (evento alterado)")
        prev, expect = l.hash, expect + 1
    return ChainVerdict(True, len(links))
