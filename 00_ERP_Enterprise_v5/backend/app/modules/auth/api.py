from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.db.session import get_session
from backend.app.modules.auth.schemas import LoginRequest,TokenResponse
from backend.app.modules.auth.application.login_service import LoginService
from backend.app.core.exceptions import AuthenticationError
router=APIRouter(prefix='/auth',tags=['auth'])
@router.post('/login',response_model=TokenResponse)
async def login(payload:LoginRequest,session:AsyncSession=Depends(get_session)):
    try: token=await LoginService().execute(session,payload.email,payload.password,payload.tenant_id)
    except AuthenticationError as exc: raise HTTPException(status_code=401,detail={'code':'AUTH_INVALID'}) from exc
    return TokenResponse(access_token=token)
