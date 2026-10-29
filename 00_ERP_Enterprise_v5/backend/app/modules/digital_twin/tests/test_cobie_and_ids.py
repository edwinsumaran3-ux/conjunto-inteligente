from backend.app.modules.digital_twin.domain.cobie import parse_cobie_asset_csv
from backend.app.modules.digital_twin.domain.bim_quality import InformationRequirement, evaluate_requirements

def test_cobie_csv_is_deterministic():
    rows=parse_cobie_asset_csv('Name,ExternalId,AssetType\nPump P1,ASSET-1,Pump\n')
    assert rows[0]['ExternalId']=='ASSET-1'

def test_ids_checks_property_presence_and_value():
    req=InformationRequirement('IFCPUMP','Pset_Asset.SerialNumber',True,('SN-1',))
    out=evaluate_requirements([{'express_id':1,'entity_type':'IFCPUMP','properties':{'Pset_Asset.SerialNumber':'SN-1'}}],[req])
    assert out[0].status=='PASS'
