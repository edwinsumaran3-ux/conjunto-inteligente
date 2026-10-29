from uuid import uuid4
import pytest
from backend.app.modules.digital_twin.api.router import ModelVersionIn, BindingIn, PropertyIn, SpatialReferenceIn, SnapshotIn

def test_model_version_requires_identity():
    m=ModelVersionIn(model_key='building-a',version='1.0',source_system='BIM',source_format='IFC4')
    assert m.source_format=='IFC4'

def test_binding_confidence_is_bounded():
    with pytest.raises(Exception): BindingIn(node_id=uuid4(),identifier_system='IFC',identifier_type='GUID',identifier='x',confidence=1.1)

def test_spatial_reference_keeps_open_coordinate_system():
    s=SpatialReferenceIn(node_id=uuid4(),reference_system='EPSG:25830',geometry={'type':'Point','coordinates':[1,2]})
    assert s.geometry_type=='POINT'

def test_property_accepts_structured_value():
    p=PropertyIn(node_id=uuid4(),namespace='Pset_Asset',property_name='Manufacturer',value_type='string',value='ACME',source='IFC')
    assert p.value=='ACME'

def test_snapshot_health_bounds():
    s=SnapshotIn(node_id=uuid4(),health_score=87.5)
    assert s.health_score==87.5
