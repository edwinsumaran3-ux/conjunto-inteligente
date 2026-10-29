import pytest
from pydantic import ValidationError
from app.schemas.diagnostic import DiagnosticRequest


def test_diagnostic_request():
    request = DiagnosticRequest(asset_id="A-1", observation="noise", tenant_id="T-1")
    assert request.asset_id == "A-1"
    assert request.request_id is not None


def test_diagnostic_rejects_extra_fields():
    with pytest.raises(ValidationError):
        DiagnosticRequest(
            asset_id="A-1", observation="noise", tenant_id="T-1", unexpected=True
        )
