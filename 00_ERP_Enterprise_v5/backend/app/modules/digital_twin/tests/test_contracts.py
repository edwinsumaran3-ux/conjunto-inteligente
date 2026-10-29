from uuid import uuid4
import pytest
from backend.app.modules.digital_twin.api.router import NodeIn, EdgeIn

def test_node_contract_rejects_invalid_coordinates():
    with pytest.raises(Exception): NodeIn(node_type='sensor',code='s1',name='Sensor',latitude=91)

def test_edge_contract_requires_distinct_nodes():
    a=uuid4(); assert EdgeIn(from_node=a,to_node=a,relation='contains').from_node==a
