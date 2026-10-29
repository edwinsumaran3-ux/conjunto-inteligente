from backend.app.modules.digital_twin.domain.ifc_ingestion import parse_ifc_step
from backend.app.modules.digital_twin.domain.bim_geometry import extract_placements,validate_spatial_model
S="ISO-10303-21;HEADER;FILE_SCHEMA(('IFC4X3_ADD2'));ENDSEC;DATA;#1=IFCPROJECT('P',$,'Project',$,$,$,$,(#2),$);#2=IFCSITE('S',$,'Site',$,$,#10,$,$,.ELEMENT.,$,$,$,$,$);#3=IFCBUILDING('B',$,'Building',$,$,#11,$,$,.ELEMENT.,$);#4=IFCBUILDINGSTOREY('L1',$,'Level 1',$,$,#12,$,$,.ELEMENT.,0.,$);#5=IFCSPACE('R1',$,'Room',$,$,#13,$,$,.ELEMENT.,$);#10=IFCLOCALPLACEMENT(#20,$);#11=IFCLOCALPLACEMENT(#20,#10);#12=IFCLOCALPLACEMENT(#20,#11);#13=IFCLOCALPLACEMENT(#20,#12);#20=IFCAXIS2PLACEMENT3D(#21,$,$);#21=IFCCARTESIANPOINT((100.,200.,0.));#30=IFCRELAGGREGATES('r',$,$,$,#2,(#3));#31=IFCRELAGGREGATES('r2',$,$,$,#3,(#4));#32=IFCRELAGGREGATES('r3',$,$,$,#4,(#5));ENDSEC;END-ISO-10303-21;"
def test_spatial_hierarchy_and_world_location():
 p=parse_ifc_step(S); g=extract_placements(p); assert len(g["spatial_elements"])==5; assert g["placements"][5]["location"]==(400.,800.,0.); assert len(g["containment"])==3
def test_spatial_validation():
 r=validate_spatial_model(parse_ifc_step(S)); assert r["valid"] and not r["missing_project"]
