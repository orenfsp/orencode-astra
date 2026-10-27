import asyncio
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth_models import AuthSession, Role, User
from app.auth_security import login_limiter, token_hash, utcnow, verify_password
from app.database import get_session
from app.main import app
from app.models import Base


class AuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_directory = tempfile.TemporaryDirectory()
        path = Path(cls.temp_directory.name) / "auth.db"
        cls.engine = create_async_engine(f"sqlite+aiosqlite:///{path.as_posix()}", poolclass=NullPool)
        cls.session_factory = async_sessionmaker(cls.engine, expire_on_commit=False)

        async def prepare() -> None:
            async with cls.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with cls.session_factory() as session:
                session.add_all([Role(name=name) for name in ("athlete", "coach", "judge", "federation_admin")])
                await session.commit()
        asyncio.run(prepare())

        async def test_session():
            async with cls.session_factory() as session:
                yield session
        app.dependency_overrides[get_session] = test_session
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        app.dependency_overrides.clear()
        asyncio.run(cls.engine.dispose())
        cls.temp_directory.cleanup()

    def setUp(self) -> None:
        self.client.cookies.clear()
        login_limiter.clear()

    def register(self, email: str, role: str = "athlete", password: str = "Correct-Horse-42", admin_registration_code: str | None = None):
        return self.client.post("/api/v1/auth/register", json={"email": email, "password": password, "role": role, "admin_registration_code": admin_registration_code, "last_name": "Иванова", "first_name": "Анна", "pd_consent": True})

    def test_register_normalizes_email_hashes_password_and_sets_cookie_flags(self) -> None:
        response = self.register("  Mixed.Auth@Example.COM  ")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["email"], "mixed.auth@example.com")
        self.assertEqual(response.json()["roles"], ["athlete"])
        cookies = response.headers.get_list("set-cookie")
        session_cookie = next(item for item in cookies if item.startswith("fsp_session="))
        self.assertIn("HttpOnly", session_cookie)
        self.assertIn("SameSite=lax", session_cookie)
        self.assertIn("Path=/", session_cookie)
        self.assertNotIn("Secure", session_cookie)

        async def inspect() -> tuple[str, str]:
            async with self.session_factory() as db:
                user = await db.scalar(select(User).where(User.email == "mixed.auth@example.com"))
                return user.email, user.password_hash
        email, password_hash = asyncio.run(inspect())
        self.assertEqual(email, "mixed.auth@example.com")
        self.assertTrue(password_hash.startswith("$argon2id$"))
        self.assertNotIn("Correct-Horse-42", password_hash)
        self.assertTrue(verify_password(password_hash, "Correct-Horse-42"))

    def test_secure_cookie_flag_can_be_enabled(self) -> None:
        with patch.dict("os.environ", {"AUTH_COOKIE_SECURE": "true"}):
            response = self.register("secure-cookie@example.com")
        cookies = response.headers.get_list("set-cookie")
        self.assertIn("Secure", next(item for item in cookies if item.startswith("fsp_session=")))
        self.assertIn("Secure", next(item for item in cookies if item.startswith("fsp_csrf=")))

    def test_duplicate_email_has_generic_registration_error(self) -> None:
        self.assertEqual(self.register("duplicate@example.com").status_code, 201)
        response = self.register("DUPLICATE@example.com")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "Не удалось зарегистрировать аккаунт")

    def test_admin_registration_requires_configured_code(self) -> None:
        response = self.register("admin-self@example.com", role="federation_admin")
        self.assertEqual(response.status_code, 403)
        with patch.dict("os.environ", {"ADMIN_REGISTRATION_CODE": "local-admin-code"}):
            wrong = self.register("admin-wrong@example.com", role="federation_admin", admin_registration_code="wrong")
            created = self.register("admin-ok@example.com", role="federation_admin", admin_registration_code="local-admin-code")
        self.assertEqual(wrong.status_code, 403)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["active_role"], "federation_admin")

    def test_login_success_failure_and_me(self) -> None:
        self.register("login@example.com")
        self.client.cookies.clear()
        wrong_email = self.client.post("/api/v1/auth/login", json={"email": "missing@example.com", "password": "wrong"})
        wrong_password = self.client.post("/api/v1/auth/login", json={"email": "login@example.com", "password": "wrong"})
        self.assertEqual(wrong_email.status_code, 401)
        self.assertEqual(wrong_email.json(), wrong_password.json())
        success = self.client.post("/api/v1/auth/login", json={"email": "LOGIN@example.com", "password": "Correct-Horse-42"})
        self.assertEqual(success.status_code, 200)
        self.assertNotIn("password", str(success.json()).lower())
        self.assertEqual(self.client.get("/api/v1/auth/me").json()["email"], "login@example.com")

    def test_logout_requires_csrf_and_revokes_session(self) -> None:
        self.register("logout@example.com")
        session_token = self.client.cookies.get("fsp_session")
        self.assertEqual(self.client.post("/api/v1/auth/logout").status_code, 403)
        csrf = self.client.cookies.get("fsp_csrf")
        response = self.client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
        self.assertEqual(response.status_code, 204)
        self.client.cookies.set("fsp_session", session_token)
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)

    def test_expired_session_is_rejected_and_cleaned(self) -> None:
        self.register("expired@example.com")
        raw_token = self.client.cookies.get("fsp_session")

        async def expire() -> None:
            async with self.session_factory() as db:
                item = await db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(raw_token)))
                item.expires_at = utcnow() - timedelta(seconds=1)
                await db.commit()
        asyncio.run(expire())
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)
        async def count_expired() -> int:
            async with self.session_factory() as db:
                return len(list((await db.scalars(select(AuthSession).where(AuthSession.token_hash == token_hash(raw_token)))).all()))
        self.assertEqual(asyncio.run(count_expired()), 0)

    def test_switch_role_only_when_assigned(self) -> None:
        self.register("roles@example.com")
        csrf = self.client.cookies.get("fsp_csrf")
        forbidden = self.client.post("/api/v1/auth/role", json={"role": "coach"}, headers={"X-CSRF-Token": csrf})
        self.assertEqual(forbidden.status_code, 403)

        async def assign() -> None:
            async with self.session_factory() as db:
                user = await db.scalar(select(User).where(User.email == "roles@example.com"))
                coach = await db.scalar(select(Role).where(Role.name == "coach"))
                user.roles.append(coach)
                await db.commit()
        asyncio.run(assign())
        switched = self.client.post("/api/v1/auth/role", json={"role": "coach"}, headers={"X-CSRF-Token": csrf})
        self.assertEqual(switched.status_code, 200)
        self.assertEqual(switched.json()["active_role"], "coach")
        self.assertEqual(switched.json()["roles"], ["athlete", "coach"])

    def test_login_prefers_assigned_federation_admin_role(self) -> None:
        self.register("promoted@example.com")
        self.client.cookies.clear()

        async def promote() -> None:
            async with self.session_factory() as db:
                user = await db.scalar(select(User).where(User.email == "promoted@example.com"))
                admin = await db.scalar(select(Role).where(Role.name == "federation_admin"))
                user.roles.append(admin)
                await db.commit()

        asyncio.run(promote())
        logged_in = self.client.post(
            "/api/v1/auth/login",
            json={"email": "promoted@example.com", "password": "Correct-Horse-42"},
        )
        self.assertEqual(logged_in.status_code, 200)
        self.assertEqual(logged_in.json()["roles"], ["athlete", "federation_admin"])
        self.assertEqual(logged_in.json()["active_role"], "federation_admin")

    def test_registration_requires_pd_consent_and_creates_profile(self) -> None:
        refused = self.client.post("/api/v1/auth/register", json={"email": "no-consent@example.com", "password": "Correct-Horse-42", "last_name": "А", "first_name": "Б", "pd_consent": False})
        self.assertEqual(refused.status_code, 422)
        created = self.register("consent@example.com")
        self.assertEqual(created.json()["full_name"], "Иванова Анна")

        async def inspect():
            async with self.session_factory() as db:
                return await db.scalar(select(User).where(User.email == "consent@example.com"))
        self.assertIsNotNone(asyncio.run(inspect()).pd_consent_at)

    def test_user_adds_public_role_and_switches_without_relogin(self) -> None:
        self.register("multi@example.com")
        csrf = self.client.cookies.get("fsp_csrf")
        self.assertEqual(self.client.post("/api/v1/auth/roles", json={"role": "coach"}).status_code, 403)
        self.assertEqual(self.client.post("/api/v1/auth/roles", json={"role": "federation_admin"}, headers={"X-CSRF-Token": csrf}).status_code, 422)
        added = self.client.post("/api/v1/auth/roles", json={"role": "coach"}, headers={"X-CSRF-Token": csrf})
        self.assertEqual(added.status_code, 200)
        self.assertEqual(added.json()["roles"], ["athlete", "coach"])
        self.assertEqual(added.json()["active_role"], "coach")
        back = self.client.post("/api/v1/auth/role", json={"role": "athlete"}, headers={"X-CSRF-Token": csrf})
        self.assertEqual(back.json()["active_role"], "athlete")
        again = self.client.post("/api/v1/auth/roles", json={"role": "coach"}, headers={"X-CSRF-Token": csrf})
        self.assertEqual(again.json()["roles"], ["athlete", "coach"])

    def test_login_limiter(self) -> None:
        for _ in range(5):
            response = self.client.post("/api/v1/auth/login", json={"email": "limited@example.com", "password": "wrong"})
            self.assertEqual(response.status_code, 401)
        blocked = self.client.post("/api/v1/auth/login", json={"email": "limited@example.com", "password": "wrong"})
        self.assertEqual(blocked.status_code, 429)


if __name__ == "__main__":
    unittest.main()
