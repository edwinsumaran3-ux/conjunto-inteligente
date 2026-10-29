from backend.app.modules.estate.api.router import PROPERTY_TYPES, PropertyIn, EventIn

def test_property_catalog_is_not_building_only():
    assert {'house','farm','rural_property','housing_block','residential_complex','campus'} <= PROPERTY_TYPES

def test_property_requires_root_and_identity():
    x=PropertyIn(root_node_id='00000000-0000-0000-0000-000000000001',property_type='farm',code='F-01',name='Finca')
    assert x.property_type=='farm'

def test_event_requires_idempotency():
    x=EventIn(event_type='intrusion',source_type='sensor',idempotency_key='tenant:event:1',observed_at='2026-10-04T00:00:00Z')
    assert x.idempotency_key
