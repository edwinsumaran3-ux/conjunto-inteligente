from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.providers.deterministic import DeterministicProvider


def test_specialized_api_serializes_request_id_as_uuid_string(monkeypatch):
    monkeypatch.setenv("AI__INTERNAL_SERVICE_TOKEN", "")
    monkeypatch.setattr(
        "app.api.specialized.get_provider", lambda: DeterministicProvider()
    )
    get_settings.cache_clear()
    request_id = uuid4()

    try:
        response = TestClient(app).post(
            "/analyze/plan",
            json={
                "request_id": str(request_id),
                "tenant_id": "tenant-test",
                "message": "Summarize the supplied evidence.",
            },
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    serialized_id = response.json()["request_id"]
    assert isinstance(serialized_id, str)
    assert UUID(serialized_id) == request_id
