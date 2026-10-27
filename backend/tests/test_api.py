import asyncio
import tempfile
import unittest
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth_models import Role, User
from app.auth_security import hash_password, utcnow
from app.database import get_session
from app.main import app
from app.models import Base, Competition, CompetitionStatus


COMPETITIONS = [
    Competition(
        id=3,
        title="Data Science Challenge",
        discipline="Программирование систем искусственного интеллекта",
        date=date(2026, 10, 10),
        location="Онлайн",
        description="Соревнование по анализу данных.",
        event_format="Онлайн",
        registration_start=date(2026, 9, 1),
        registration_end=date(2026, 10, 5),
        is_archived=False,
        status=CompetitionStatus.COMPLETED,
    ),
    Competition(
        id=1,
        title="Кубок города по программированию",
        discipline="Алгоритмическое программирование",
        date=date(2026, 11, 15),
        location="Оренбург",
        description="Региональный алгоритмический турнир.",
        event_format="Очно",
        registration_start=date(2026, 10, 15),
        registration_end=date(2026, 11, 10),
        is_archived=False,
        status=CompetitionStatus.REGISTRATION_OPEN,
    ),
    Competition(
        id=2,
        title="Осенний хакатон",
        discipline="Продуктовое программирование",
        date=date(2026, 11, 28),
        location="Самара",
        description="Командная разработка продукта.",
        event_format="Гибридный",
        registration_start=date(2026, 10, 20),
        registration_end=date(2026, 11, 20),
        is_archived=False,
        status=CompetitionStatus.UPCOMING,
    ),
]


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_directory = tempfile.TemporaryDirectory()
        database_path = Path(cls.temp_directory.name) / "test.db"
        cls.engine = create_async_engine(
            f"sqlite+aiosqlite:///{database_path.as_posix()}",
            poolclass=NullPool,
        )
        cls.session_factory = async_sessionmaker(cls.engine, expire_on_commit=False)

        async def prepare_database() -> None:
            async with cls.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with cls.session_factory() as session:
                session.add_all(COMPETITIONS)
                roles = [Role(name=name) for name in ("athlete", "coach", "judge", "federation_admin")]
                session.add_all(roles)
                session.add(
                    User(
                        email="api-admin@example.test",
                        password_hash=hash_password("Api-Admin-Password-42"),
                        created_at=utcnow(),
                        roles=[roles[-1]],
                    )
                )
                await session.commit()
            await cls.engine.dispose()

        asyncio.run(prepare_database())

        async def test_get_session():
            async with cls.session_factory() as session:
                yield session

        app.dependency_overrides[get_session] = test_get_session
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        app.dependency_overrides.clear()
        asyncio.run(cls.engine.dispose())
        cls.temp_directory.cleanup()

    def setUp(self) -> None:
        self.client.cookies.clear()

    def admin_headers(self) -> dict[str, str]:
        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": "api-admin@example.test", "password": "Api-Admin-Password-42"},
        )
        self.assertEqual(response.status_code, 200)
        return {"X-CSRF-Token": self.client.cookies.get("fsp_csrf")}

    def test_health(self) -> None:
        response = self.client.get("/api/v1/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_competitions_are_sorted_by_id(self) -> None:
        response = self.client.get("/api/v1/competitions")

        self.assertEqual(response.status_code, 200)
        competitions = response.json()
        self.assertEqual([item["id"] for item in competitions], [1, 2, 3])
        self.assertEqual(competitions[0]["date"], "2026-11-15")
        self.assertEqual(competitions[0]["status"], "registration_open")
        self.assertEqual(competitions[0]["event_format"], "Очно")
        self.assertFalse(competitions[0]["is_archived"])

    def test_filter_by_status(self) -> None:
        response = self.client.get(
            "/api/v1/competitions",
            params={"status": "upcoming"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()], [2])

    def test_filter_by_discipline(self) -> None:
        response = self.client.get(
            "/api/v1/competitions",
            params={"discipline": "Алгоритмическое программирование"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()], [1])

    def test_filter_by_title_query(self) -> None:
        response = self.client.get(
            "/api/v1/competitions",
            params={"q": "science"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()], [3])

    def test_combined_filters(self) -> None:
        response = self.client.get(
            "/api/v1/competitions",
            params={
                "status": "registration_open",
                "discipline": "Алгоритмическое программирование",
                "q": "Кубок",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()], [1])

    def test_filters_can_return_empty_list(self) -> None:
        response = self.client.get(
            "/api/v1/competitions",
            params={
                "status": "completed",
                "discipline": "Продуктовое программирование",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_invalid_status_returns_422(self) -> None:
        response = self.client.get(
            "/api/v1/competitions",
            params={"status": "unknown"},
        )

        self.assertEqual(response.status_code, 422)

    def test_empty_discipline_returns_422(self) -> None:
        response = self.client.get(
            "/api/v1/competitions",
            params={"discipline": ""},
        )

        self.assertEqual(response.status_code, 422)

    def test_competition_by_id(self) -> None:
        response = self.client.get("/api/v1/competitions/2")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], 2)
        self.assertEqual(response.json()["title"], "Осенний хакатон")

    def test_competition_by_id_returns_404(self) -> None:
        response = self.client.get("/api/v1/competitions/999")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Competition not found"})

    def test_create_update_status_close_and_archive(self) -> None:
        headers = self.admin_headers()
        payload = {
            "title": "Новый турнир",
            "discipline": "Алгоритмическое программирование",
            "date": "2026-12-20",
            "location": "Бузулук",
            "description": "Тестовое событие для проверки управления.",
            "event_format": "Очно",
            "registration_start": "2026-11-01",
            "registration_end": "2026-12-10",
            "status": "draft",
        }
        created = self.client.post("/api/v1/competitions", json=payload, headers=headers)
        self.assertEqual(created.status_code, 201)
        competition_id = created.json()["id"]

        updated = self.client.patch(
            f"/api/v1/competitions/{competition_id}",
            json={"location": "Оренбург", "description": "Обновлённое описание"},
            headers=headers,
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["location"], "Оренбург")

        published = self.client.patch(
            f"/api/v1/competitions/{competition_id}/status",
            json={"status": "registration_open"},
            headers=headers,
        )
        self.assertEqual(published.status_code, 200)
        self.assertEqual(published.json()["status"], "registration_open")

        closed = self.client.post(
            f"/api/v1/competitions/{competition_id}/close-registration",
            headers=headers,
        )
        self.assertEqual(closed.status_code, 200)
        self.assertEqual(closed.json()["status"], "registration_closed")

        archived = self.client.post(f"/api/v1/competitions/{competition_id}/archive", headers=headers)
        self.assertEqual(archived.status_code, 200)
        self.assertTrue(archived.json()["is_archived"])

        public_ids = [item["id"] for item in self.client.get("/api/v1/competitions").json()]
        self.assertNotIn(competition_id, public_ids)
        admin_ids = [
            item["id"]
            for item in self.client.get(
                "/api/v1/competitions", params={"include_archived": "true"}
            ).json()
        ]
        self.assertIn(competition_id, admin_ids)
        self.assertEqual(
            self.client.get(f"/api/v1/competitions/{competition_id}").status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                f"/api/v1/competitions/{competition_id}",
                params={"include_archived": "true"},
            ).status_code,
            200,
        )

    def test_management_validation(self) -> None:
        headers = self.admin_headers()
        invalid_dates = {
            "title": "Некорректный турнир",
            "discipline": "Дисциплина",
            "date": "2026-11-01",
            "location": "Оренбург",
            "description": "Описание",
            "event_format": "Очно",
            "registration_start": "2026-10-01",
            "registration_end": "2026-11-02",
            "status": "draft",
        }
        self.assertEqual(
            self.client.post("/api/v1/competitions", json=invalid_dates, headers=headers).status_code,
            422,
        )
        self.assertEqual(
            self.client.patch(
                "/api/v1/competitions/2/status", json={"status": "not-a-status"}, headers=headers
            ).status_code,
            422,
        )
        self.assertEqual(
            self.client.post("/api/v1/competitions/2/close-registration", headers=headers).status_code,
            409,
        )

    def test_write_endpoints_require_admin_and_csrf(self) -> None:
        payload = {
            "title": "Запрещённый турнир", "discipline": "Дисциплина",
            "date": "2026-12-20", "location": "Оренбург", "description": "Описание",
            "event_format": "Очно", "registration_start": "2026-11-01",
            "registration_end": "2026-12-01", "status": "draft",
        }
        self.assertEqual(self.client.post("/api/v1/competitions", json=payload).status_code, 401)
        registered = self.client.post(
            "/api/v1/auth/register",
            json={"email": "not-admin@example.test", "password": "Not-Admin-Password-42", "role": "athlete"},
        )
        self.assertEqual(registered.status_code, 201)
        csrf = self.client.cookies.get("fsp_csrf")
        self.assertEqual(
            self.client.post("/api/v1/competitions", json=payload, headers={"X-CSRF-Token": csrf}).status_code,
            403,
        )
        self.client.cookies.clear()
        admin_headers = self.admin_headers()
        self.assertEqual(self.client.post("/api/v1/competitions", json=payload, headers=admin_headers).status_code, 201)
        self.assertEqual(self.client.patch("/api/v1/competitions/2", json={"location": "Бугуруслан"}, headers={}).status_code, 403)

    def test_non_positive_id_returns_422(self) -> None:
        response = self.client.get("/api/v1/competitions/0")

        self.assertEqual(response.status_code, 422)

    def test_vite_origin_is_allowed(self) -> None:
        response = self.client.options(
            "/api/v1/competitions",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://localhost:5173",
        )


if __name__ == "__main__":
    unittest.main()
