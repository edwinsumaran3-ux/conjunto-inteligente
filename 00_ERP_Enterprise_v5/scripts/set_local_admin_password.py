"""Update one development admin without placing credentials in source or SQL."""
from __future__ import annotations

import asyncio
import os

import asyncpg
from backend.app.core.security import hash_password


async def main() -> None:
    if os.getenv("APP_ENV", "development") != "development":
        raise RuntimeError("This helper is restricted to development environments")

    values = {
        name: os.getenv(name, "")
        for name in ("CI_USER_ID", "CI_TENANT_ID", "CI_CURRENT_EMAIL", "CI_EMAIL", "CI_NEW_PASSWORD")
    }
    if any(not value for value in values.values()):
        raise RuntimeError("Explicit user, tenant, email, and password values are required")
    if len(values["CI_NEW_PASSWORD"]) < 12:
        raise RuntimeError("The new password must contain at least 12 characters")

    url = os.getenv("MIGRATION_DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://", 1)
    if not url:
        raise RuntimeError("MIGRATION_DATABASE_URL is required")

    conn = await asyncpg.connect(url)
    try:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.current_tenant_id', $1, true)", values["CI_TENANT_ID"])
            result = await conn.execute(
                "UPDATE users SET email=$1, password_hash=$2 "
                "WHERE id=$3::uuid AND tenant_id=$4::uuid AND email=$5",
                values["CI_EMAIL"],
                hash_password(values["CI_NEW_PASSWORD"]),
                values["CI_USER_ID"],
                values["CI_TENANT_ID"],
                values["CI_CURRENT_EMAIL"],
            )
            if result != "UPDATE 1":
                raise RuntimeError("Expected exactly one user matching id, tenant, and current email")
    finally:
        await conn.close()

    print("Development admin updated.")


if __name__ == "__main__":
    asyncio.run(main())