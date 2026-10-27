"""Explicit dev/demo admin bootstrap: ADMIN_EMAIL=... ADMIN_PASSWORD=... python -m app.create_admin."""

import asyncio
import os

from sqlalchemy import select

from app.auth_models import Role, User
from app.auth_security import hash_password, normalize_email, utcnow
from app.database import SessionFactory


async def create_admin() -> None:
    email = normalize_email(os.environ.get("ADMIN_EMAIL", ""))
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not email or "@" not in email:
        raise SystemExit("ADMIN_EMAIL must be a valid email")
    if len(password) < 12 or len(password) > 128:
        raise SystemExit("ADMIN_PASSWORD must contain 12-128 characters")

    async with SessionFactory() as db:
        role = await db.scalar(select(Role).where(Role.name == "federation_admin"))
        if role is None:
            role = Role(name="federation_admin")
            db.add(role)
            await db.flush()
        user = await db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, password_hash=hash_password(password), created_at=utcnow(), roles=[role])
            db.add(user)
        elif role not in user.roles:
            user.roles.append(role)
        await db.commit()
    print(f"Federation admin is ready: {email}")


if __name__ == "__main__":
    asyncio.run(create_admin())
