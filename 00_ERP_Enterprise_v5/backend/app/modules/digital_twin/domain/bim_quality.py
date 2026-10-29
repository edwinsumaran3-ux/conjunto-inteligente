from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class InformationRequirement:
    entity_type: str
    property_name: str
    required: bool=True
    allowed_values: tuple[str,...]=()

@dataclass(frozen=True)
class RequirementResult:
    entity_type: str
    property_name: str
    status: str
    reason: str


def evaluate_requirements(entities: list[dict], requirements: list[InformationRequirement]) -> list[RequirementResult]:
    out=[]
    for req in requirements:
        matched=[e for e in entities if e.get('entity_type')==req.entity_type]
        if not matched:
            out.append(RequirementResult(req.entity_type,req.property_name,'NOT_APPLICABLE','no matching IFC entities'))
            continue
        for e in matched:
            props=e.get('properties') or {}
            if req.property_name not in props:
                out.append(RequirementResult(req.entity_type,req.property_name,'FAIL','required property missing'))
            elif req.allowed_values and str(props[req.property_name]) not in req.allowed_values:
                out.append(RequirementResult(req.entity_type,req.property_name,'FAIL','value outside allowed set'))
            else:
                out.append(RequirementResult(req.entity_type,req.property_name,'PASS','requirement satisfied'))
    return out
