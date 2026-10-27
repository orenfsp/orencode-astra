import unittest
from datetime import date

from fastapi.testclient import TestClient

from app.database import get_session
from app.main import app
from app.models import Competition, CompetitionStatus


class FakeScalarResult:
    def all(self) -> list[Competition]:
        return [
            Competition(
                id=1,
                title="Кубок города по программированию",
                discipline="Алгоритмическое программирование",
                date=date(2026, 11, 15),
                location="Оренбург",
                status=CompetitionStatus.REGISTRATION_OPEN,
            ),
            Competition(
                id=2,
                title="Осенний хакатон",
                discipline="Продуктовое программирование",
                date=date(2026, 11, 28),
                location="Самара",
                status=CompetitionStatus.UPCOMING,
            ),
            Competition(
                id=3,
                title="Data Science Challenge",
                discipline="Программирование систем искусственного интеллекта",
                date=date(2026, 10, 10),
                location="Онлайн",
                status=CompetitionStatus.COMPLETED,
            ),
        ]


class FakeSession:
    async def scalars(self, statement: object) -> FakeScalarResult:
        return FakeScalarResult()


async def fake_get_session():
    yield FakeSession()


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        app.dependency_overrides[get_session] = fake_get_session
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides.clear()

    def test_health(self) -> None:
        response = self.client.get("/api/v1/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_competitions(self) -> None:
        response = self.client.get("/api/v1/competitions")

        self.assertEqual(response.status_code, 200)
        competitions = response.json()
        self.assertEqual(len(competitions), 3)
        self.assertEqual(competitions[0]["id"], 1)
        self.assertEqual(competitions[0]["date"], "2026-11-15")
        self.assertEqual(competitions[0]["status"], "registration_open")
        self.assertEqual(
            set(competitions[0]),
            {"id", "title", "discipline", "date", "location", "status"},
        )

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
