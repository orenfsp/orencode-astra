import unittest

from fastapi.testclient import TestClient

from app.main import app


class ApiTests(unittest.TestCase):
    client = TestClient(app)

    def test_health(self) -> None:
        response = self.client.get("/api/v1/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_competitions(self) -> None:
        response = self.client.get("/api/v1/competitions")

        self.assertEqual(response.status_code, 200)
        competitions = response.json()
        self.assertEqual(len(competitions), 3)
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
