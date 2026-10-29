import pathlib
from backend.app.modules.digital_twin.domain.ifc_ingestion import parse_ifc_step, decode_step_string

SAMPLE = pathlib.Path(__file__).resolve().parents[5] / "frontend" / "bim" / "public" / "torre_demo.ifc"

def test_step_unicode_escapes_decoded():
    assert decode_step_string("presurizaci\\X2\\00F3\\X0\\n") == "presurización"
    assert decode_step_string("a\\X\\F1o") == "año"

def test_real_ifc_names_and_property_keys():
    p = parse_ifc_step(SAMPLE.read_text())
    pump = next(e for e in p["entities_dict"] if e["entity_type"] == "IFCPUMP")
    assert pump["name"] == "Bomba de presurización B1"
    assert pump["properties"] == {"Pset_ManufacturerTypeInformation.Manufacturer": "ACME",
                                  "Pset_ManufacturerTypeInformation.ModelLabel": "P-100"}
