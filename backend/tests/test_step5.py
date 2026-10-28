import asyncio
import unittest
from unittest.mock import patch

from sqlalchemy import func, select

from app.application_models import Application
from app.audit_models import AuditEntry
from app.auth_models import Role, User
from app.auth_security import hash_password, login_limiter, utcnow
from app.demo import MARKER, load_demo
from app.models import Competition
from support import ApiDatabase, csrf, register


ADMIN = ("step5-admin@example.test", "Step5-Admin-Password-42")


async def seed_admin(session) -> None:
    admin = await session.scalar(select(Role).where(Role.name == "federation_admin"))
    session.add(User(email=ADMIN[0], password_hash=hash_password(ADMIN[1]), created_at=utcnow(), roles=[admin]))


class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.db = ApiDatabase("step5-audit")
        cls.client = cls.db.prepare(seed_admin)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.db.close(cls.client)

    def setUp(self) -> None:
        self.client.cookies.clear()
        login_limiter.clear()

    def test_changes_are_logged_with_author_and_role(self) -> None:
        register(self.client, "audited@example.test", last_name="Журналов")
        athlete_id = self.client.get("/api/v1/auth/me").json()["id"]
        self.client.put("/api/v1/me/profile", json={"last_name": "Журналов", "first_name": "Тест", "birth_date": "2000-01-01"}, headers=csrf(self.client))
        self.client.put("/api/v1/me/athlete", json={"discipline_ids": [1]}, headers=csrf(self.client))
        self.client.post("/api/v1/auth/roles", json={"role": "coach"}, headers=csrf(self.client))

        self.client.cookies.clear()
        self.client.post("/api/v1/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]})
        headers = csrf(self.client)
        body = {
            "title": "Журналируемый турнир", "discipline_id": 1, "competition_type_id": 1, "level": "regional", "age_group_ids": [3],
            "date": "2026-12-20", "end_date": "2026-12-20", "location": "Оренбург", "description": "Тест", "format": "offline",
            "registration_start": "2026-11-01", "registration_end": "2026-12-10", "calendar_plan": "none", "status": "draft",
        }
        competition_id = self.client.post("/api/v1/competitions", json=body, headers=headers).json()["id"]
        self.client.patch(f"/api/v1/competitions/{competition_id}", json={"location": "Орск"}, headers=headers)
        self.client.patch(f"/api/v1/competitions/{competition_id}/status", json={"status": "registration_open"}, headers=headers)
        self.client.post("/api/v1/sanctions", json={"athlete_id": athlete_id, "kind": "suspension", "starts_on": "2026-01-01", "reason": "Проверка журнала"}, headers=headers)

        page = self.client.get("/api/v1/audit", params={"entity_type": "Соревнование"}).json()
        actions = [(item["action"], item["user_name"], item["role"]) for item in page["items"]]
        self.assertEqual(actions[-1][2], "federation_admin")
        self.assertEqual([item["action"] for item in page["items"]], ["status", "update", "create"])
        update = page["items"][1]
        self.assertEqual(update["changes"]["location"], ["Оренбург", "Орск"])
        self.assertIn("статус registration_open", page["items"][0]["summary"].replace("draft → ", ""))

        everything = self.client.get("/api/v1/audit", params={"limit": 200}).json()
        types = set(everything["entity_types"])
        self.assertTrue({"Аккаунт", "Профиль", "Соревнование", "Дисквалификация / отстранение"} <= types, types)
        registration = next(item for item in everything["items"] if item["entity_type"] == "Аккаунт" and item["action"] == "create")
        self.assertEqual(registration["user_id"], athlete_id)
        self.assertNotIn("password_hash", registration["changes"])
        roles_change = next(item for item in everything["items"] if item["entity_type"] == "Аккаунт" and item["action"] == "update")
        self.assertEqual(roles_change["changes"]["roles"], [["athlete"], ["athlete", "coach"]])
        self.assertEqual(self.client.get("/api/v1/audit", params={"q": "Журналируемый"}).json()["total"], 3)

        self.client.cookies.clear()
        self.client.post("/api/v1/auth/login", json={"email": "audited@example.test", "password": "Correct-Horse-42"})
        self.assertEqual(self.client.get("/api/v1/audit").status_code, 403)


class DemoDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.db = ApiDatabase("step5-demo")
        cls.client = cls.db.prepare()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.db.close(cls.client)

    def test_demo_covers_six_disciplines_and_two_years(self) -> None:
        async def audit_count() -> int:
            async with self.db.session_factory() as db:
                return await db.scalar(select(func.count()).select_from(AuditEntry))
        audit_before = asyncio.run(audit_count())
        with patch("app.demo.SessionFactory", self.db.session_factory):
            message = asyncio.run(load_demo())
            again = asyncio.run(load_demo())
        self.assertIn("Загружено", message)
        self.assertEqual(again, "Демо-данные уже загружены")

        async def stats():
            async with self.db.session_factory() as db:
                years = set(await db.scalars(select(func.extract("year", Competition.date)).where(Competition.protocol_published_at.is_not(None))))
                disciplines = set(await db.scalars(select(Competition.discipline_id).where(Competition.protocol_published_at.is_not(None))))
                applications = await db.scalar(select(func.count()).select_from(Application))
                return years, disciplines, applications
        years, disciplines, applications = asyncio.run(stats())
        self.assertTrue({2024, 2025} <= {int(year) for year in years})
        self.assertEqual(len(disciplines), 6)
        self.assertGreater(applications, 200)
        self.assertEqual(asyncio.run(audit_count()), audit_before)  # демо-данные не пишутся в журнал

        login_limiter.clear()
        login = self.client.post("/api/v1/auth/login", json={"email": MARKER, "password": "Demo-Password-2026"})
        self.assertEqual(login.status_code, 200)
        rating = self.client.get("/api/v1/rating", params={"discipline_id": 1, "season": 2025}).json()
        self.assertGreater(len(rating["rows"]), 5)
        headcount = self.client.get("/api/v1/reports/headcount", params={"from_year": 2024, "to_year": 2026}).json()
        self.assertGreater(headcount["total"][-1], headcount["total"][0])
        self.assertEqual(len([line for line in next(section for section in headcount["sections"] if section["key"] == "disciplines")["rows"]]), 6)
        dashboard = self.client.get("/api/v1/admin/dashboard").json()
        self.assertGreater(dashboard["ranks_this_year"] + len(self.client.get("/api/v1/rank-requests").json()), 0)

        multi = self.client.post("/api/v1/auth/login", json={"email": "coach-judge@demo.fsp56.test", "password": "Demo-Password-2026"}).json()
        self.assertEqual(multi["roles"], ["coach", "judge"])


if __name__ == "__main__":
    unittest.main()
