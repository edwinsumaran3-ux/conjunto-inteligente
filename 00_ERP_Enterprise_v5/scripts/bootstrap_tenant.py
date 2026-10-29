"""Crea un tenant y su primer administrador (necesario en una instalación nueva: nadie puede iniciar sesión sin esto).
Uso: BOOTSTRAP_DATABASE_URL=postgresql://propietario@host/db python scripts/bootstrap_tenant.py --name "Mi Conjunto" --email admin@x.co [--password ...]
Con rol propietario/superusuario (se ejecuta fuera de RLS). Si no se da --password se genera una y se imprime UNA vez."""
import argparse, asyncio, os, secrets, sys, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import asyncpg
from backend.app.core.security import hash_password

async def bootstrap(url: str, name: str, email: str, password: str | None) -> dict:
    password = password or secrets.token_urlsafe(18)
    if len(password) < 12: raise SystemExit("la contraseña requiere 12+ caracteres")
    c = await asyncpg.connect(url.replace("postgresql+asyncpg://", "postgresql://", 1))
    try:
        async with c.transaction():
            tid = await c.fetchval("INSERT INTO tenants(name) VALUES($1) RETURNING id", name)
            await c.execute("SELECT set_config('app.current_tenant_id',$1,true)", str(tid))
            uid = await c.fetchval("INSERT INTO users(tenant_id,email,password_hash) VALUES($1,$2,$3) RETURNING id", tid, email.lower(), hash_password(password))
            rid = await c.fetchval("INSERT INTO roles(tenant_id,name) VALUES($1,'admin') RETURNING id", tid)
            await c.execute("INSERT INTO user_roles(user_id,role_id) VALUES($1,$2)", uid, rid)
    finally: await c.close()
    return {"tenant_id": str(tid), "user_id": str(uid), "email": email.lower(), "password": password}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--name", required=True); ap.add_argument("--email", required=True); ap.add_argument("--password")
    a = ap.parse_args(); out = asyncio.run(bootstrap(os.environ["BOOTSTRAP_DATABASE_URL"], a.name, a.email, a.password))
    print(f"tenant_id={out['tenant_id']}\nadmin={out['email']}\npassword={out['password']}  (guárdala: no se vuelve a mostrar)")
