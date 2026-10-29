"""Temporal failure-chain reasoning for the engineering digital twin.

This module ranks evidence links between operational anomalies. It deliberately
uses the terms precursor, propagation candidate and correlation rather than
claiming automated root-cause proof.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime
from math import exp
from typing import Iterable, Mapping

@dataclass(frozen=True)
class FailureLink:
    source_anomaly: str
    target_anomaly: str
    relation: str
    time_gap_seconds: float
    dependency_factor: float
    confidence: float
    evidence: tuple[str, ...]

@dataclass(frozen=True)
class FailureChain:
    ordered_anomalies: tuple[str, ...]
    links: tuple[FailureLink, ...]
    confidence: float
    claim_level: str


def _parse_time(value) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _dependency_factor(source: str, target: str, relations: Iterable[Mapping], max_depth: int = 8) -> float:
    if source == target:
        return 1.0
    adjacency: dict[str, list[tuple[str, float]]] = {}
    for rel in relations:
        a, b = str(rel["source"]), str(rel["target"])
        if a == b:
            continue
        factor = max(0.0, min(1.0, float(rel.get("criticality", 1.0)) * float(rel.get("propagation_factor", 1.0))))
        adjacency.setdefault(a, []).append((b, factor))
    frontier = [(source, 1.0, 0)]
    best = {source: 1.0}
    while frontier:
        node, score, depth = frontier.pop(0)
        if depth >= max_depth:
            continue
        for nxt, factor in adjacency.get(node, []):
            value = score * factor
            if value <= best.get(nxt, 0.0):
                continue
            best[nxt] = value
            if nxt == target:
                return value
            frontier.append((nxt, value, depth + 1))
    return 0.0


def build_failure_chain(events: Iterable[Mapping], relations: Iterable[Mapping], max_gap_seconds: float = 3600.0) -> FailureChain:
    rows = []
    for event in events:
        aid = str(event["anomaly_id"])
        rows.append({**event, "anomaly_id": aid, "detected_at": _parse_time(event["detected_at"])})
    rows.sort(key=lambda x: (x["detected_at"], x["anomaly_id"]))
    if not rows:
        return FailureChain((), (), 0.0, "correlation_only")

    links: list[FailureLink] = []
    for left, right in zip(rows, rows[1:]):
        gap = (right["detected_at"] - left["detected_at"]).total_seconds()
        if gap < 0 or gap > max_gap_seconds:
            continue
        dep = _dependency_factor(str(left["node_id"]), str(right["node_id"]), relations)
        temporal = exp(-gap / max(1.0, max_gap_seconds))
        relation = "dependency_propagation_candidate" if dep > 0 else "temporal_precursor_candidate"
        confidence = max(0.0, min(1.0, temporal * (0.55 + 0.45 * dep)))
        evidence = [f"temporal_gap_seconds={round(gap,3)}"]
        if dep > 0:
            evidence.append(f"dependency_factor={round(dep,6)}")
        evidence.append("root_cause_not_proven")
        links.append(FailureLink(left["anomaly_id"], right["anomaly_id"], relation, round(gap,3), round(dep,6), round(confidence,6), tuple(evidence)))

    confidence = sum(x.confidence for x in links) / len(links) if links else 0.0
    return FailureChain(tuple(x["anomaly_id"] for x in rows), tuple(links), round(confidence,6), "correlation_with_dependency_evidence")


def to_dict(chain: FailureChain) -> dict:
    return {
        "ordered_anomalies": list(chain.ordered_anomalies),
        "links": [asdict(link) for link in chain.links],
        "confidence": chain.confidence,
        "claim_level": chain.claim_level,
    }
