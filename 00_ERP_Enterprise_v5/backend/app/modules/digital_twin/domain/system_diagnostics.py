"""System-level digital-twin diagnosis primitives.

Deterministic, auditable aggregation and dependency-impact propagation. This module
never claims causal certainty; it ranks propagation paths and system health evidence.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from typing import Iterable, Mapping

@dataclass(frozen=True)
class ImpactPath:
    origin: str
    target: str
    relation: str
    depth: int
    impact: float
    criticality: float

@dataclass(frozen=True)
class SystemAssessment:
    health_score: float
    severity: str
    confidence: float
    impacted_nodes: tuple[str, ...]
    critical_paths: tuple[ImpactPath, ...]


def _severity(score: float) -> str:
    if score < 30: return "critical"
    if score < 50: return "high"
    if score < 70: return "medium"
    if score < 90: return "low"
    return "info"


def aggregate_health(node_health: Mapping[str, float], weights: Mapping[str, float] | None = None,
                     confidence: Mapping[str, float] | None = None) -> SystemAssessment:
    if not node_health:
        raise ValueError("NO_NODE_HEALTH")
    weights = weights or {}
    confidence = confidence or {}
    items=[]
    for node, raw in node_health.items():
        value=float(raw)
        if not isfinite(value) or not 0 <= value <= 100:
            raise ValueError("INVALID_NODE_HEALTH")
        weight=max(0.0,float(weights.get(node,1.0)))
        if weight == 0: continue
        conf=min(1.0,max(0.0,float(confidence.get(node,1.0))))
        items.append((node,value,weight,conf))
    if not items: raise ValueError("NO_WEIGHTED_NODES")
    total=sum(v*w for _,v,w,_ in items)
    denom=sum(w for _,_,w,_ in items)
    score=total/denom
    conf=sum(c*w for _,_,w,c in items)/denom
    return SystemAssessment(round(score,3),_severity(score),round(conf,3),tuple(),tuple())


def propagate_impact(origin: str, relations: Iterable[Mapping], origin_impact: float=1.0,
                     max_depth: int=8, min_impact: float=0.10) -> tuple[ImpactPath, ...]:
    if not 0 <= origin_impact <= 1: raise ValueError("INVALID_ORIGIN_IMPACT")
    adjacency: dict[str,list[Mapping]]={}
    for r in relations:
        src=str(r["source"]); dst=str(r["target"])
        if src == dst: continue
        adjacency.setdefault(src,[]).append(r)
    queue=[(origin,0,origin_impact)]
    best={origin:origin_impact}; paths=[]
    while queue:
        src,depth,impact=queue.pop(0)
        if depth>=max_depth: continue
        for rel in adjacency.get(src,[]):
            dst=str(rel["target"])
            criticality=min(1.0,max(0.0,float(rel.get("criticality",1.0))))
            factor=min(1.0,max(0.0,float(rel.get("propagation_factor",1.0))))
            next_impact=impact*criticality*factor
            if next_impact < min_impact: continue
            previous=best.get(dst,0.0)
            if next_impact <= previous: continue
            best[dst]=next_impact
            paths.append(ImpactPath(origin,dst,str(rel.get("relation","depends_on")),depth+1,round(next_impact,6),round(criticality,6)))
            queue.append((dst,depth+1,next_impact))
    return tuple(sorted(paths,key=lambda p:(-p.impact,p.depth,p.target)))
