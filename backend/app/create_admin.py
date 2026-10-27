"""Explicit dev/demo admin bootstrap: ADMIN_EMAIL=... ADMIN_PASSWORD=... python -m app.create_admin."""

import asyncio
import os

from sqlalchemy import select, update

from app.auth_models import AuthSession, Role, User
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
            action = "created"
        else:
            user.password_hash = hash_password(password)
            if role not in user.roles:
                user.roles.append(role)
                action = "promoted"
            else:
                action = "updated"
            # The explicit password reset invalidates old browser sessions. A fresh
            # login will select federation_admin as the active role.
            await db.execute(
                update(AuthSession)
                .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
                .values(revoked_at=utcnow())
            )
        await db.commit()
    print(f"Federation admin {action}: {email}. Sign in again to activate federation_admin.")


if __name__ == "__main__":
    asyncio.run(create_admin())
