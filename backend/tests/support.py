"""Shared SQLite test database for API tests."""

import asyncio
import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.application_models  # noqa: F401 - registers application tables
import app.coaching_models  # noqa: F401 - registers coach links
import app.notification_models  # noqa: F401 - registers notifications
import app.profile_models  # noqa: F401 - registers profile tables
import app.qualification_models  # noqa: F401 - registers judges and ranks
import app.rating_models  # noqa: F401 - registers rating, sanctions and teams
import app.audit_models  # noqa: F401 - registers the audit log
from app.auth_models import Role
from app.database import get_session
from app.main import app
from app.models import Base
from app.reference_data import seed_rank_norms, seed_rating, seed_reference


PASSWORD = "Correct-Horse-42"


class ApiDatabase:
    def __init__(self, name: str) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        path = Path(self.temp_directory.name) / f"{name}.db"
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{path.as_posix()}", poolclass=NullPool)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        os.environ["UPLOAD_DIR"] = str(Path(self.temp_directory.name) / "uploads")

    def prepare(self, extra=None) -> TestClient:
        async def run() -> None:
            async with self.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with self.session_factory() as session:
                session.add_all([Role(name=name) for name in ("athlete", "coach", "judge", "federation_admin")])
                await seed_reference(session)
                await seed_rank_norms(session)
                await seed_rating(session)
                if extra is not None:
                    await extra(session)
                await session.commit()
        asyncio.run(run())

        async def test_session():
            async with self.session_factory() as session:
                yield session

        app.dependency_overrides[get_session] = test_session
        return TestClient(app)

    def close(self, client: TestClient) -> None:
        client.close()
        app.dependency_overrides.clear()
        asyncio.run(self.engine.dispose())
        self.temp_directory.cleanup()


def register(client: TestClient, email: str, role: str = "athlete", password: str = PASSWORD, **extra):
    body = {"email": email, "password": password, "role": role, "last_name": "Тестов", "first_name": "Тест", "pd_consent": True}
    body.update(extra)
    return client.post("/api/v1/auth/register", json=body)


def csrf(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("fsp_csrf")}
