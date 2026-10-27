import os
import unittest

from fastapi.testclient import TestClient

from app.main import app


@unittest.skipUnless(
    os.getenv("RUN_POSTGRES_INTEGRATION") == "1",
    "set RUN_POSTGRES_INTEGRATION=1 with a migrated and seeded PostgreSQL database",
)
class PostgresIntegrationTests(unittest.TestCase):
    def test_competitions_are_read_from_postgres(self) -> None:
        response = TestClient(app).get("/api/v1/competitions")

        self.assertEqual(response.status_code, 200)
        competitions = response.json()
        self.assertEqual([item["id"] for item in competitions], [1, 2, 3])
        self.assertEqual(
            [item["status"] for item in competitions],
            ["registration_open", "upcoming", "completed"],
        )
        self.assertEqual(competitions[0]["date"], "2026-11-15")


if __name__ == "__main__":
    unittest.main()
