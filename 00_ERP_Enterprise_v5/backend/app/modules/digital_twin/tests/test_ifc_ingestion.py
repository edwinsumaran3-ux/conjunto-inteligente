from backend.app.modules.digital_twin.domain.ifc_ingestion import parse_ifc_step, validate_ifc

S='''ISO-10303-21;HEADER;FILE_SCHEMA(('IFC4X3_ADD2'));ENDSEC;DATA;#1=IFCPROJECT('0PROJ',$,'Project',$,$,$,$,(#2),$);#2=IFCSITE('0SITE',$,'Site',$,$,$,$,$,.ELEMENT.,$,$,$,$,$);#3=IFCBUILDING('0BLDG',$,'Building',$,$,$,$,$,.ELEMENT.,$,$);#4=IFCSPACE('0SP',$,'Room 101',$,$,$,$,$,.ELEMENT.,$);#5=IFCRELAGGREGATES('0REL',$,$,$,#1,(#2));#6=IFCRELAGGREGATES('0REL2',$,$,$,#2,(#3));ENDSEC;END-ISO-10303-21;'''

def test_parse_ifc_schema_and_entities():
    p=parse_ifc_step(S)
    assert p['schema']=='IFC4X3_ADD2'
    assert p['entity_count']==6
    assert p['entity_types']['IFCBUILDING']==1

def test_ifc_validation_required_types():
    r=validate_ifc(S,required_types=['IFCPROJECT','IFCBUILDING'])
    assert r['valid'] is True

def test_ifc_validation_reports_missing_type():
    r=validate_ifc(S,required_types=['IFCFACILITY'])
    assert r['valid'] is False
    assert r['missing_required_types']==['IFCFACILITY']

def test_nested_step_arguments_are_preserved():
    p=parse_ifc_step(S)
    project=p['by_id'][1]
    assert '#2' in project.args[7]
