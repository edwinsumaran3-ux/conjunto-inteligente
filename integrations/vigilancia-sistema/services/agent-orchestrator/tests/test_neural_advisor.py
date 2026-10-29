import os,sys,asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from neural_advisor import NeuralAdvisor
from models import Incident

def test_advisor_is_optional_without_gateway(monkeypatch):
    monkeypatch.delenv("AI_GATEWAY_URL", raising=False)
    incident=Incident(incident_id="i",correlation_key="c",severity="LOW",kind="MOTION",details={})
    assert asyncio.run(NeuralAdvisor().advise(incident)) is None
