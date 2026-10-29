"""Deterministic, dependency-light IFC STEP inspection for the Digital Twin.
Supports IFC STEP text inspection without pretending to be a full geometry kernel.
For full geometry/solid processing a certified IFC engine remains an explicit boundary.
"""
from __future__ import annotations
import hashlib, re
from dataclasses import dataclass
from typing import Any

_ENTITY_RE = re.compile(r"#(\d+)\s*=\s*([A-Z0-9_]+)\s*\((.*?)\)\s*;", re.S)
_QUOTED_RE = re.compile(r"'(?:''|[^'])*'")

@dataclass(frozen=True)
class IfcEntity:
    express_id: int
    entity_type: str
    args: tuple[str, ...]
    global_id: str | None
    name: str | None
    object_type: str | None
    references: tuple[int, ...]


def _split_top_level(text: str) -> list[str]:
    out=[]; start=0; depth=0; quoted=False; i=0
    while i < len(text):
        ch=text[i]
        if ch=="'":
            if quoted and i+1<len(text) and text[i+1]=="'": i += 2; continue
            quoted=not quoted
        elif not quoted:
            if ch=='(': depth += 1
            elif ch==')': depth -= 1
            elif ch==',' and depth==0:
                out.append(text[start:i].strip()); start=i+1
        i += 1
    tail=text[start:].strip()
    if tail or text.strip()=='': out.append(tail)
    return out


_X2_RE = re.compile(r"\\X2\\((?:[0-9A-Fa-f]{4})+)\\X0\\")
_X4_RE = re.compile(r"\\X4\\((?:[0-9A-Fa-f]{8})+)\\X0\\")
_X_RE = re.compile(r"\\X\\([0-9A-Fa-f]{2})")

def decode_step_string(text: str) -> str:
    """Decodifica escapes ISO 10303-21: \\X2\\00F3\\X0\\ (UTF-16), \\X4\\ (UTF-32), \\X\\F3 (Latin-1)."""
    text=_X2_RE.sub(lambda m: ''.join(chr(int(m.group(1)[i:i+4],16)) for i in range(0,len(m.group(1)),4)), text)
    text=_X4_RE.sub(lambda m: ''.join(chr(int(m.group(1)[i:i+8],16)) for i in range(0,len(m.group(1)),8)), text)
    text=_X_RE.sub(lambda m: chr(int(m.group(1),16)), text)
    return text.replace('\\\\','\\')

def _unquote(value: str) -> str | None:
    value=value.strip()
    if value in ('$','*',''): return None
    if value.startswith("'") and value.endswith("'"):
        return decode_step_string(value[1:-1].replace("''", "'"))
    return None

def _typed_value(raw: str) -> str | None:
    """IFCLABEL('ACME') -> 'ACME'; IFCREAL(1.5) -> '1.5'; $ -> None."""
    raw=raw.strip()
    if raw in ('$','*',''): return None
    m=re.fullmatch(r"[A-Z0-9_]+\((.*)\)", raw, re.S)
    inner=m.group(1).strip() if m else raw
    q=_unquote(inner)
    return q if q is not None else inner


def _refs(value: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"#(\d+)", value))


def _iter_step_entities(content: str):
    """Yield (express_id, entity_type, argument_text) with balanced STEP parentheses."""
    i=0; n=len(content)
    while i<n:
        if content[i]=='#':
            j=i+1
            while j<n and content[j].isdigit(): j+=1
            if j>i+1 and j<n and content[j]=='=':
                eid=int(content[i+1:j]); k=j+1
                while k<n and content[k].isspace(): k+=1
                t0=k
                while k<n and (content[k].isalnum() or content[k]=='_'): k+=1
                typ=content[t0:k].upper()
                while k<n and content[k].isspace(): k+=1
                if k<n and content[k]=='(':
                    depth=1; q=False; x=k+1
                    while x<n and depth:
                        ch=content[x]
                        if ch=="'":
                            if q and x+1<n and content[x+1]=="'": x+=2; continue
                            q=not q
                        elif not q:
                            if ch=='(': depth+=1
                            elif ch==')': depth-=1
                        x+=1
                    if depth==0:
                        yield eid,typ,content[k+1:x-1]
                        i=x
                        continue
        i+=1

def parse_ifc_step(content: str) -> dict[str, Any]:
    if not isinstance(content, str) or len(content.strip()) < 20:
        raise ValueError('IFC content is empty or too short')
    schema_match=re.search(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'", content, re.I)
    schema=schema_match.group(1).upper() if schema_match else None
    if 'ISO-10303-21' not in content[:500].upper():
        raise ValueError('not an IFC STEP physical file')
    entities=[]
    for eid,typ,args_text in _iter_step_entities(content):
        args=tuple(_split_top_level(args_text))
        gid=_unquote(args[0]) if args and typ.startswith('IFC') else None
        name=_unquote(args[2]) if len(args)>2 and typ.startswith('IFC') else None
        object_type=_unquote(args[4]) if len(args)>4 and typ.startswith('IFCOBJECT') else None
        entities.append(IfcEntity(eid,typ,args,gid,name,object_type,_refs(args_text)))
    if not entities: raise ValueError('IFC contains no STEP entities')
    by_id={e.express_id:e for e in entities}
    relations=[]
    property_values={}; psets={}
    for e in entities:
        if e.entity_type=='IFCPROPERTYSINGLEVALUE' and len(e.args)>=3:
            pname=_unquote(e.args[0])
            if pname: property_values[e.express_id]=(pname,_typed_value(e.args[2]))
        elif e.entity_type=='IFCPROPERTYSET' and len(e.args)>=5:
            pname=_unquote(e.args[2]) or f'PSET_{e.express_id}'
            psets[e.express_id]=(pname,_refs(e.args[4]))
    object_props={}
    for e in entities:
        if e.entity_type=='IFCRELAGGREGATES' and len(e.args)>=6:
            parent=_refs(e.args[4]); children=_refs(e.args[5])
            relations += [(e.express_id,'aggregates',p,c) for p in parent for c in children]
        elif e.entity_type=='IFCRELCONTAINEDINSPATIALSTRUCTURE' and len(e.args)>=6:
            children=_refs(e.args[4]); parent=_refs(e.args[5])
            relations += [(e.express_id,'contains',p,c) for p in parent for c in children]
        elif e.entity_type=='IFCRELDEFINESBYPROPERTIES' and len(e.args)>=6:
            props=_refs(e.args[5]); objects=_refs(e.args[4])
            relations += [(e.express_id,'defines_properties',o,p) for o in objects for p in props]
            for obj in objects:
                bucket=object_props.setdefault(obj,{})
                for psref in props:
                    ps=psets.get(psref)
                    if ps:
                        psname, proprefs=ps
                        for pref in proprefs:
                            if pref in property_values:
                                pn,pv=property_values[pref]; bucket[f'{psname}.{pn}']=pv
    enriched=[{'express_id':e.express_id,'entity_type':e.entity_type,'global_id':e.global_id,'name':e.name,'object_type':e.object_type,'references':list(e.references),'properties':object_props.get(e.express_id,{})} for e in entities]
    return {'schema':schema,'sha256':hashlib.sha256(content.encode('utf-8')).hexdigest(),'entity_count':len(entities),'entity_types':{t:sum(1 for e in entities if e.entity_type==t) for t in sorted({e.entity_type for e in entities})},'entities':entities,'entities_dict':enriched,'relations':relations,'by_id':by_id}


def validate_ifc(content: str, *, required_types: list[str] | None=None) -> dict[str, Any]:
    parsed=parse_ifc_step(content)
    required={x.upper() for x in (required_types or [])}
    present=set(parsed['entity_types'])
    missing=sorted(required-present)
    return {'valid': not missing, 'schema': parsed['schema'], 'sha256': parsed['sha256'], 'entity_count': parsed['entity_count'], 'missing_required_types': missing, 'entity_types': parsed['entity_types']}
