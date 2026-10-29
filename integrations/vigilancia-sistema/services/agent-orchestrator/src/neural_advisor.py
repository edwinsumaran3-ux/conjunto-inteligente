from __future__ import annotations
import os
import httpx
from models import Incident

class NeuralAdvisor:
    """Optional advisory integration. Failure never blocks deterministic agents."""
    def __init__(self):
        self.base=os.getenv('CONJUNTO_AI_URL', os.getenv('AI_GATEWAY_URL','')).rstrip('/')
        self.timeout=float(os.getenv('AI_ADVISOR_TIMEOUT_S','4'))
        self.service_token=os.getenv('CONJUNTO_AI_SERVICE_TOKEN','')

    async def advise(self, incident: Incident) -> dict | None:
        if not self.base:
            return None
        body={
            'tenant_id': os.getenv('TENANT_ID','default-tenant'),
            'purpose':'event_analysis',
            'prompt': f'Analyze this monitoring incident for engineering triage: kind={incident.kind}, severity={incident.severity}. Do not propose physical actions.',
            'context': {'incident_id':incident.incident_id,'correlation_key':incident.correlation_key,'kind':incident.kind,'severity':incident.severity,'details':incident.details},
            'max_output_tokens':600,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                headers={'Authorization': f'Bearer {self.service_token}'} if self.service_token else {}
                r=await c.post(f'{self.base}/analyze/surveillance_advisor',headers=headers,json={'request_id': body['context']['incident_id'], 'tenant_id': body['tenant_id'], 'message': body['prompt'] + '\nEvidence: ' + str(body['context'])}); r.raise_for_status(); data=r.json()
            result=data.get('result') or {}; return {'status':data.get('status'),'provider':result.get('provider'),'model':result.get('model'),'text':result.get('response'),'advisory_only':True}
        except Exception:
            return {'status':'degraded','advisory_only':True,'text':None}
