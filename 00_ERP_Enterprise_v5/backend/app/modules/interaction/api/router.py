from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from backend.app.api.deps import AuthContext, get_auth_context, get_tenant_session
from backend.app.platform.realtime.service import RealtimeService
router = APIRouter(prefix='/realtime', tags=['realtime'])
service = RealtimeService()

@router.get('/events')
async def replay_events(topic: str = Query(min_length=5, max_length=160), after_sequence: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=500), auth: AuthContext = Depends(get_auth_context), session=Depends(get_tenant_session)):
    events = await service.replay(session, tenant_id=UUID(auth.tenant_id), actor_id=UUID(auth.user_id), topic=topic, after_sequence=after_sequence, limit=limit)
    return {'events':[{'event_id':str(e.event_id),'sequence':e.sequence,'topic':e.topic,'correlation_id':e.correlation_id,'payload':e.payload,'payload_sha256':e.payload_sha256} for e in events]}
