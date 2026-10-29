"""Administración de identidad por tenant: usuarios y roles. Antes NO existía ninguna forma de crear usuarios ni asignar roles."""
from __future__ import annotations
import re
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from backend.app.api.deps import AuthContext, get_auth_context, get_tenant_session
from backend.app.core.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])
ADMIN = {"admin", "administrator", "security_admin"}
ROLE = re.compile(r"^[a-z][a-z0-9_]{1,78}$")
def _admin(a: AuthContext):
    if not (ADMIN & set(a.roles)): raise HTTPException(403, {"code": "USER_ADMIN_ROLE_REQUIRED"})
def _pwd(p: str) -> str:
    if len(p) < 12 or not re.search(r"[A-Za-z]", p) or not re.search(r"\d", p): raise ValueError("la contraseña requiere 12+ caracteres, letras y números")
    return p

class UserIn(BaseModel):
    email: EmailStr; password: str = Field(min_length=12, max_length=256); roles: list[str] = Field(default_factory=list, max_length=20)
class RoleIn(BaseModel):
    role: str

async def _grant(s, t: UUID, user_id: UUID, role: str):
    if not ROLE.match(role): raise ValueError(f"nombre de rol inválido: {role}")
    rid = (await s.execute(text("INSERT INTO roles(id,tenant_id,name) VALUES(:i,:t,:n) ON CONFLICT(tenant_id,name) DO UPDATE SET name=EXCLUDED.name RETURNING id"), {"i": uuid4(), "t": t, "n": role})).scalar_one()
    await s.execute(text("INSERT INTO user_roles(user_id,role_id) VALUES(:u,:r) ON CONFLICT DO NOTHING"), {"u": user_id, "r": rid})

@router.post("", status_code=201)
async def create_user(r: UserIn, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    _admin(a); t = UUID(a.tenant_id); uid = uuid4(); _pwd(r.password)
    await s.execute(text("INSERT INTO users(id,tenant_id,email,password_hash) VALUES(:i,:t,:e,:h)"), {"i": uid, "t": t, "e": r.email.lower(), "h": hash_password(r.password)})
    for role in sorted(set(r.roles)): await _grant(s, t, uid, role)
    await s.execute(text("INSERT INTO audit_log(id,tenant_id,actor_id,action,entity_type,entity_id,after_state) VALUES(:i,:t,:a,'user.created','User',:e,CAST(:s AS jsonb))"),
                    {"i": uuid4(), "t": t, "a": UUID(a.user_id), "e": str(uid), "s": '{"email":"%s","roles":%s}' % (r.email.lower(), str(sorted(set(r.roles))).replace("'", '"'))})
    return {"id": str(uid), "email": r.email.lower(), "roles": sorted(set(r.roles))}

@router.get("")
async def list_users(a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    _admin(a)
    rows = (await s.execute(text("""SELECT u.id,u.email,u.is_active,COALESCE(array_agg(r.name ORDER BY r.name) FILTER (WHERE r.name IS NOT NULL),'{}') AS roles
        FROM users u LEFT JOIN user_roles ur ON ur.user_id=u.id LEFT JOIN roles r ON r.id=ur.role_id WHERE u.tenant_id=:t GROUP BY u.id ORDER BY u.email"""), {"t": UUID(a.tenant_id)})).mappings().all()
    return [{"id": str(x["id"]), "email": x["email"], "is_active": x["is_active"], "roles": list(x["roles"])} for x in rows]

@router.post("/{user_id}/roles", status_code=204)
async def add_role(user_id: UUID, r: RoleIn, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    _admin(a); t = UUID(a.tenant_id)
    if not (await s.execute(text("SELECT 1 FROM users WHERE id=:u AND tenant_id=:t"), {"u": user_id, "t": t})).first(): raise HTTPException(404, "user not found")
    await _grant(s, t, user_id, r.role)

@router.delete("/{user_id}/roles/{role}", status_code=204)
async def remove_role(user_id: UUID, role: str, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    _admin(a); t = UUID(a.tenant_id)
    if str(user_id) == a.user_id and role in ADMIN: raise HTTPException(409, {"code": "CANNOT_REMOVE_OWN_ADMIN_ROLE"})
    await s.execute(text("DELETE FROM user_roles USING roles r WHERE user_roles.role_id=r.id AND r.tenant_id=:t AND r.name=:n AND user_roles.user_id=:u"), {"t": t, "n": role, "u": user_id})

@router.post("/{user_id}/deactivate", status_code=204)
async def deactivate(user_id: UUID, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    _admin(a)
    if str(user_id) == a.user_id: raise HTTPException(409, {"code": "CANNOT_DEACTIVATE_SELF"})
    if (await s.execute(text("UPDATE users SET is_active=false WHERE id=:u AND tenant_id=:t"), {"u": user_id, "t": UUID(a.tenant_id)})).rowcount == 0: raise HTTPException(404, "user not found")
