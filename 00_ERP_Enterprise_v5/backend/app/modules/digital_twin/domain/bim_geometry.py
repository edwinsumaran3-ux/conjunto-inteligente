from __future__ import annotations
from typing import Any
import math,re
SPATIAL_TYPES={"IFCPROJECT","IFCSITE","IFCBUILDING","IFCBUILDINGSTOREY","IFCSPACE","IFCZONE","IFCROAD","IFCBRIDGE","IFCRAILWAY","IFCFACILITY"}
def _refs(v): return [int(x) for x in re.findall(r"#(\d+)",v or "")]
def _nums(v): return tuple(float(x) for x in re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[Ee][-+]?\d+)?",v or ""))
def _I(): return (1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.)
def _mm(a,b): return tuple(sum(a[r*4+k]*b[k*4+c] for k in range(4)) for r in range(4) for c in range(4))
def _axis(loc,az=None,rx=None):
    def norm(v):
        n=math.sqrt(sum(x*x for x in v)); return tuple(x/n for x in v) if n else None
    def cross(a,b): return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
    z=norm(az or (0.,0.,1.)) or (0.,0.,1.); x=norm(rx or (1.,0.,0.)) or (1.,0.,0.); y=norm(cross(z,x)) or (0.,1.,0.); x=norm(cross(y,z)) or x
    return (x[0],x[1],x[2],loc[0],y[0],y[1],y[2],loc[1],z[0],z[1],z[2],loc[2],0.,0.,0.,1.)
def extract_placements(parsed:dict[str,Any])->dict[str,Any]:
    points={}; dirs={}; axes={}; locals_={}; spatial=[]; placements={}
    for e in parsed["entities"]:
        if e.entity_type=="IFCCARTESIANPOINT" and e.args:
            n=_nums(e.args[0]); points[e.express_id]=tuple((n+(0.,0.,0.))[:3])
        elif e.entity_type=="IFCDIRECTION" and e.args:
            n=_nums(e.args[0]); dirs[e.express_id]=tuple((n+(0.,0.,1.))[:3])
    for e in parsed["entities"]:
        if e.entity_type=="IFCAXIS2PLACEMENT3D" and e.args:
            lr=_refs(e.args[0]); ar=_refs(e.args[1]) if len(e.args)>1 else []; rr=_refs(e.args[2]) if len(e.args)>2 else []
            axes[e.express_id]=(points.get(lr[0],(0.,0.,0.)) if lr else (0.,0.,0.),dirs.get(ar[0]) if ar else None,dirs.get(rr[0]) if rr else None)
    for e in parsed["entities"]:
        if e.entity_type=="IFCLOCALPLACEMENT" and e.args:
            ar=_refs(e.args[0]); pr=_refs(e.args[1]) if len(e.args)>1 else []; loc,az,rx=axes.get(ar[0],((0.,0.,0.),None,None)) if ar else ((0.,0.,0.),None,None); locals_[e.express_id]=(_axis(loc,az,rx),pr[0] if pr else None,loc)
    def resolve(pid,seen=None):
        seen=seen or set()
        if pid in seen or pid not in locals_: return _I()
        mat,parent,_=locals_[pid]
        if parent is None:return mat
        seen.add(pid); return _mm(resolve(parent,seen),mat)
    for e in parsed["entities"]:
        if e.entity_type in SPATIAL_TYPES: spatial.append({"express_id":e.express_id,"entity_type":e.entity_type,"global_id":e.global_id,"name":e.name})
        if len(e.args)>5:
            rr=_refs(e.args[5])
            if rr and rr[0] in locals_:
                mat=resolve(rr[0]); placements[e.express_id]={"placement_id":rr[0],"matrix":mat,"location":(mat[3],mat[7],mat[11])}
    containment=[{"relation_express_id":r[0],"relation_type":r[1],"from_express_id":r[2],"to_express_id":r[3]} for r in parsed["relations"] if r[1] in {"aggregates","contains"}]
    return {"placements":placements,"local_placements":{k:{"parent":v[1],"location":v[2]} for k,v in locals_.items()},"spatial_elements":spatial,"containment":containment}
def validate_spatial_model(parsed):
    g=extract_placements(parsed); gids=[x["global_id"] for x in g["spatial_elements"] if x.get("global_id")]; proj=any(x["entity_type"]=="IFCPROJECT" for x in g["spatial_elements"]); dups=sorted({x for x in gids if gids.count(x)>1}); return {"valid":bool(gids) and proj and not dups,"spatial_count":len(g["spatial_elements"]),"placement_count":len(g["placements"]),"containment_count":len(g["containment"]),"missing_project":not proj,"duplicate_global_ids":dups}
