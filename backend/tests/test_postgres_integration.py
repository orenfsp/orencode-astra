import os
import unittest
import uuid

from fastapi.testclient import TestClient

from app.main import app


@unittest.skipUnless(
    os.getenv("RUN_POSTGRES_INTEGRATION") == "1",
    "set RUN_POSTGRES_INTEGRATION=1 with a migrated and seeded PostgreSQL database",
)
class PostgresIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._client_context = TestClient(app)
        cls.client = cls._client_context.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._client_context.__exit__(None, None, None)

    def test_auth_round_trip_uses_postgres(self) -> None:
        email = f"integration-{uuid.uuid4().hex}@example.test"
        registered = self.client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "Postgres-Test-Password-42", "role": "coach"},
        )
        self.assertEqual(registered.status_code, 201)
        self.assertEqual(self.client.get("/api/v1/auth/me").json()["active_role"], "coach")
        csrf = self.client.cookies.get("fsp_csrf")
        self.assertEqual(self.client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}).status_code, 204)
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)

    def test_federation_admin_can_manage_competition(self) -> None:
        self.client.cookies.clear()
        login = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": "integration-admin@example.test",
                "password": "Integration-Admin-Password-42",
            },
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json()["active_role"], "federation_admin")
        csrf = self.client.cookies.get("fsp_csrf")
        created = self.client.post(
            "/api/v1/competitions",
            headers={"X-CSRF-Token": csrf},
            json={
                "title": "PostgreSQL integration tournament",
                "discipline": "Алгоритмическое программирование",
                "date": "2027-02-20",
                "location": "Оренбург",
                "description": "Проверка admin RBAC на PostgreSQL.",
                "event_format": "Очно",
                "registration_start": "2027-01-01",
                "registration_end": "2027-02-10",
                "status": "draft",
            },
        )
        self.assertEqual(created.status_code, 201)

        self.client.cookies.clear()
        athlete = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": f"athlete-{uuid.uuid4().hex}@example.test",
                "password": "Athlete-Test-Password-42",
                "role": "athlete",
            },
        )
        self.assertEqual(athlete.status_code, 201)
        athlete_csrf = self.client.cookies.get("fsp_csrf")
        denied = self.client.patch(
            f"/api/v1/competitions/{created.json()['id']}",
            json={"location": "Москва"},
            headers={"X-CSRF-Token": athlete_csrf},
        )
        self.assertEqual(denied.status_code, 403)

    def test_competitions_are_read_from_postgres(self) -> None:
        self._assert_competitions(self.client)

    def test_competition_management_round_trip_uses_postgres(self) -> None:
        logged_in = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": "integration-admin@example.test",
                "password": "Integration-Admin-Password-42",
            },
        )
        self.assertEqual(logged_in.status_code, 200)
        csrf = self.client.cookies.get("fsp_csrf")
        headers = {"X-CSRF-Token": csrf}
        marker = uuid.uuid4().hex[:8]
        created = self.client.post(
            "/api/v1/competitions",
            headers=headers,
            json={
                "title": f"PostgreSQL CRUD {marker}",
                "discipline": "Алгоритмическое программирование",
                "date": "2027-02-20",
                "location": "Оренбург",
                "description": "Integration test competition",
                "event_format": "Очно",
                "registration_start": "2027-01-01",
                "registration_end": "2027-02-10",
                "status": "draft",
            },
        )
        self.assertEqual(created.status_code, 201)
        competition_id = created.json()["id"]

        updated = self.client.patch(
            f"/api/v1/competitions/{competition_id}",
            headers=headers,
            json={"location": "Орск"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["location"], "Орск")
        opened = self.client.patch(
            f"/api/v1/competitions/{competition_id}/status",
            headers=headers,
            json={"status": "registration_open"},
        )
        self.assertEqual(opened.status_code, 200)
        closed = self.client.post(
            f"/api/v1/competitions/{competition_id}/close-registration",
            headers=headers,
        )
        self.assertEqual(closed.status_code, 200)
        self.assertEqual(closed.json()["status"], "registration_closed")
        archived = self.client.post(
            f"/api/v1/competitions/{competition_id}/archive",
            headers=headers,
        )
        self.assertEqual(archived.status_code, 200)
        self.assertTrue(archived.json()["is_archived"])

        self.assertEqual(
            self.client.get(f"/api/v1/competitions/{competition_id}").status_code,
            404,
        )
        restored_view = self.client.get(
            f"/api/v1/competitions/{competition_id}",
            params={"include_archived": "true"},
        )
        self.assertEqual(restored_view.status_code, 200)
        self.assertEqual(restored_view.json()["title"], f"PostgreSQL CRUD {marker}")

    def _assert_competitions(self, client: TestClient) -> None:
        response = client.get("/api/v1/competitions")

        self.assertEqual(response.status_code, 200)
        competitions = response.json()
        self.assertEqual([item["id"] for item in competitions], [1, 2, 3])
        self.assertEqual(
            [item["status"] for item in competitions],
            ["registration_open", "upcoming", "completed"],
        )
        self.assertEqual(competitions[0]["date"], "2026-11-15")

        filtered_response = client.get(
            "/api/v1/competitions",
            params={
                "status": "registration_open",
                "discipline": "Алгоритмическое программирование",
                "q": "город",
            },
        )
        self.assertEqual(filtered_response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in filtered_response.json()],
            [1],
        )

        empty_response = client.get(
            "/api/v1/competitions",
            params={"status": "completed", "q": "хакатон"},
        )
        self.assertEqual(empty_response.status_code, 200)
        self.assertEqual(empty_response.json(), [])

        detail_response = client.get("/api/v1/competitions/2")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["title"], "Осенний хакатон")

        missing_response = client.get("/api/v1/competitions/999")
        self.assertEqual(missing_response.status_code, 404)
        self.assertEqual(
            missing_response.json(),
            {"detail": "Competition not found"},
        )


if __name__ == "__main__":
    unittest.main()
