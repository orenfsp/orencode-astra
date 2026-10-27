import unittest
from datetime import date

from sqlalchemy import select

from app.auth_models import Role, User
from app.auth_security import hash_password, login_limiter, utcnow
from app.models import (
    AgeGroup, CalendarPlan, Competition, CompetitionFormat, CompetitionLevel, CompetitionStatus,
    CompetitionType, Discipline,
)
from support import ApiDatabase, csrf, register


ADMIN_EMAIL = "api-admin@example.test"
ADMIN_PASSWORD = "Api-Admin-Password-42"


async def seed_competitions(session) -> None:
    disciplines = {item.code: item for item in await session.scalars(select(Discipline))}
    types = {item.name: item for item in await session.scalars(select(CompetitionType))}
    groups = list(await session.scalars(select(AgeGroup).order_by(AgeGroup.sort_order)))

    def competition(id, title, code, type_name, level, group_ids, start, reg_start, reg_end, location, fmt, plan, status):
        return Competition(
            id=id, title=title, discipline=disciplines[code], competition_type=types[type_name], level=level,
            age_groups=[groups[index] for index in group_ids], date=start, end_date=start, location=location,
            description=f"Описание: {title}", format=fmt, registration_start=reg_start, registration_end=reg_end,
            calendar_plan=plan, calendar_plan_number=None, status=status, is_archived=False,
        )

    session.add_all([
        competition(3, "Data Science Challenge", "ai", "Первенство", CompetitionLevel.REGIONAL, [1],
                    date(2026, 10, 10), date(2026, 9, 1), date(2026, 10, 5), "Онлайн", CompetitionFormat.ONLINE,
                    CalendarPlan.REGIONAL, CompetitionStatus.COMPLETED),
        competition(1, "Кубок города по программированию", "algorithmic", "Кубок", CompetitionLevel.REGIONAL, [1, 2],
                    date(2026, 11, 15), date(2026, 10, 15), date(2026, 11, 10), "Оренбург", CompetitionFormat.OFFLINE,
                    CalendarPlan.REGIONAL, CompetitionStatus.REGISTRATION_OPEN),
        competition(2, "Осенний хакатон", "product", "Официальные соревнования", CompetitionLevel.INTERREGIONAL, [2],
                    date(2026, 11, 28), date(2026, 10, 20), date(2026, 11, 20), "Орск", CompetitionFormat.MIXED,
                    CalendarPlan.EKP, CompetitionStatus.UPCOMING),
    ])
    admin = await session.scalar(select(Role).where(Role.name == "federation_admin"))
    athlete = await session.scalar(select(Role).where(Role.name == "athlete"))
    session.add(User(email=ADMIN_EMAIL, password_hash=hash_password(ADMIN_PASSWORD), created_at=utcnow(), roles=[athlete, admin]))


def payload(**changes) -> dict:
    body = {
        "title": "Новый турнир",
        "discipline_id": 1,
        "competition_type_id": 1,
        "level": "regional",
        "age_group_ids": [2, 3],
        "date": "2026-12-20",
        "end_date": "2026-12-21",
        "location": "Бузулук",
        "description": "Тестовое событие для проверки управления.",
        "format": "offline",
        "registration_start": "2026-11-01",
        "registration_end": "2026-12-10",
        "calendar_plan": "regional",
        "calendar_plan_number": "КП-2026/1",
        "status": "draft",
    }
    body.update(changes)
    return body


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.db = ApiDatabase("api")
        cls.client = cls.db.prepare(seed_competitions)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.db.close(cls.client)

    def setUp(self) -> None:
        self.client.cookies.clear()
        login_limiter.clear()

    def admin_headers(self) -> dict[str, str]:
        response = self.client.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["active_role"], "federation_admin")
        return csrf(self.client)

    def test_health(self) -> None:
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_reference_bundle_has_all_six_disciplines(self) -> None:
        response = self.client.get("/api/v1/reference")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual([item["code"] for item in body["disciplines"]], ["algorithmic", "product", "security", "ai", "robotics", "uav"])
        self.assertIn("Чемпионат", [item["name"] for item in body["competition_types"]])
        self.assertGreaterEqual(len(body["age_groups"]), 3)
        self.assertIn("г. Оренбург", [item["name"] for item in body["municipalities"]])
        self.assertIn("Главный судья", [item["name"] for item in body["judge_positions"]])

    def test_competitions_are_sorted_by_date(self) -> None:
        response = self.client.get("/api/v1/competitions")
        self.assertEqual(response.status_code, 200)
        competitions = response.json()
        self.assertEqual([item["id"] for item in competitions], [3, 1, 2])
        first = competitions[1]
        self.assertEqual(first["discipline"]["code"], "algorithmic")
        self.assertEqual(first["competition_type"]["name"], "Кубок")
        self.assertEqual(first["format"], "offline")
        self.assertEqual([group["min_age"] for group in first["age_groups"]], [14, 16])
        self.assertIsNone(first["regulation_filename"])

    def test_filters(self) -> None:
        def ids(**params):
            response = self.client.get("/api/v1/competitions", params=params)
            self.assertEqual(response.status_code, 200)
            return [item["id"] for item in response.json()]

        self.assertEqual(ids(status="upcoming"), [2])
        self.assertEqual(ids(discipline_id=1), [1])
        self.assertEqual(ids(level="interregional"), [2])
        self.assertEqual(ids(calendar_plan="ekp"), [2])
        self.assertEqual(ids(age_group_id=3), [1, 2])
        self.assertEqual(ids(q="science"), [3])
        self.assertEqual(ids(q="100%"), [])
        self.assertEqual(ids(status="registration_open", discipline_id=1, q="Кубок"), [1])
        self.assertEqual(ids(status="completed", discipline_id=2), [])

    def test_invalid_filters_return_422(self) -> None:
        self.assertEqual(self.client.get("/api/v1/competitions", params={"status": "unknown"}).status_code, 422)
        self.assertEqual(self.client.get("/api/v1/competitions", params={"discipline_id": 0}).status_code, 422)
        self.assertEqual(self.client.get("/api/v1/competitions/0").status_code, 422)

    def test_competition_by_id(self) -> None:
        response = self.client.get("/api/v1/competitions/2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Осенний хакатон")
        self.assertEqual(response.json()["calendar_plan"], "ekp")
        missing = self.client.get("/api/v1/competitions/999")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json(), {"detail": "Соревнование не найдено"})

    def test_create_update_status_close_and_archive(self) -> None:
        headers = self.admin_headers()
        created = self.client.post("/api/v1/competitions", json=payload(), headers=headers)
        self.assertEqual(created.status_code, 201, created.text)
        competition_id = created.json()["id"]
        self.assertEqual(created.json()["calendar_plan_number"], "КП-2026/1")

        updated = self.client.patch(
            f"/api/v1/competitions/{competition_id}",
            json={"location": "Оренбург", "age_group_ids": [1], "discipline_id": 6},
            headers=headers,
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["location"], "Оренбург")
        self.assertEqual([group["id"] for group in updated.json()["age_groups"]], [1])
        self.assertEqual(updated.json()["discipline"]["code"], "uav")

        published = self.client.patch(f"/api/v1/competitions/{competition_id}/status", json={"status": "registration_open"}, headers=headers)
        self.assertEqual(published.json()["status"], "registration_open")
        closed = self.client.post(f"/api/v1/competitions/{competition_id}/close-registration", headers=headers)
        self.assertEqual(closed.json()["status"], "registration_closed")
        archived = self.client.post(f"/api/v1/competitions/{competition_id}/archive", headers=headers)
        self.assertTrue(archived.json()["is_archived"])

        self.assertNotIn(competition_id, [item["id"] for item in self.client.get("/api/v1/competitions").json()])
        self.assertIn(competition_id, [item["id"] for item in self.client.get("/api/v1/competitions", params={"include_archived": "true"}).json()])
        self.assertEqual(self.client.get(f"/api/v1/competitions/{competition_id}").status_code, 404)
        self.assertEqual(self.client.patch(f"/api/v1/competitions/{competition_id}", json={"location": "Орск"}, headers=headers).status_code, 409)

    def test_management_validation(self) -> None:
        headers = self.admin_headers()
        cases = [
            payload(registration_end="2026-12-25"),
            payload(end_date="2026-12-19"),
            payload(level="regional", calendar_plan="ekp"),
            payload(level="all_russian", calendar_plan="regional"),
            payload(age_group_ids=[]),
            payload(discipline_id=99),
            payload(competition_type_id=99),
            payload(age_group_ids=[1, 99]),
            payload(format="hybrid"),
        ]
        for body in cases:
            with self.subTest(body=body):
                self.assertEqual(self.client.post("/api/v1/competitions", json=body, headers=headers).status_code, 422)
        self.assertEqual(self.client.patch("/api/v1/competitions/2", json={"end_date": "2020-01-01"}, headers=headers).status_code, 422)
        self.assertEqual(self.client.patch("/api/v1/competitions/2/status", json={"status": "not-a-status"}, headers=headers).status_code, 422)
        self.assertEqual(self.client.post("/api/v1/competitions/2/close-registration", headers=headers).status_code, 409)

    def test_write_endpoints_require_admin_and_csrf(self) -> None:
        self.assertEqual(self.client.post("/api/v1/competitions", json=payload()).status_code, 401)
        self.assertEqual(register(self.client, "not-admin@example.test").status_code, 201)
        self.assertEqual(self.client.post("/api/v1/competitions", json=payload(), headers=csrf(self.client)).status_code, 403)
        self.assertEqual(self.client.post("/api/v1/reference/competition-types", json={"name": "Турнир"}, headers=csrf(self.client)).status_code, 403)
        self.client.cookies.clear()
        admin_headers = self.admin_headers()
        self.assertEqual(self.client.post("/api/v1/competitions", json=payload(title="Разрешённый"), headers=admin_headers).status_code, 201)
        self.assertEqual(self.client.patch("/api/v1/competitions/2", json={"location": "Бугуруслан"}, headers={}).status_code, 403)

    def test_drafts_and_archive_are_visible_only_to_federation(self) -> None:
        headers = self.admin_headers()
        draft_id = self.client.post("/api/v1/competitions", json=payload(title="Черновик для проверки видимости"), headers=headers).json()["id"]
        self.assertIn(draft_id, [item["id"] for item in self.client.get("/api/v1/competitions").json()])
        self.assertEqual(self.client.get(f"/api/v1/competitions/{draft_id}").status_code, 200)

        self.client.cookies.clear()
        self.assertNotIn(draft_id, [item["id"] for item in self.client.get("/api/v1/competitions", params={"include_archived": "true"}).json()])
        self.assertEqual(self.client.get(f"/api/v1/competitions/{draft_id}").status_code, 404)
        register(self.client, "curious-athlete@example.test")
        self.assertEqual(self.client.get(f"/api/v1/competitions/{draft_id}").status_code, 404)

    def test_admin_extends_dictionaries(self) -> None:
        headers = self.admin_headers()
        created = self.client.post("/api/v1/reference/competition-types", json={"name": "Спартакиада"}, headers=headers)
        self.assertEqual(created.status_code, 201)
        duplicate = self.client.post("/api/v1/reference/competition-types", json={"name": "Спартакиада"}, headers=headers)
        self.assertEqual(duplicate.status_code, 409)
        renamed = self.client.put(f"/api/v1/reference/competition-types/{created.json()['id']}", json={"name": "Спартакиада школьников", "is_active": False}, headers=headers)
        self.assertEqual(renamed.json(), {"id": created.json()["id"], "name": "Спартакиада школьников", "is_active": False})

        group = self.client.post("/api/v1/reference/age-groups", json={"name": "Юниоры (18–25 лет)", "min_age": 18, "max_age": 25}, headers=headers)
        self.assertEqual(group.status_code, 201)
        self.assertEqual(self.client.post("/api/v1/reference/age-groups", json={"name": "Ошибка", "min_age": 20, "max_age": 10}, headers=headers).status_code, 422)

        organization = self.client.post("/api/v1/reference/organizations", json={"name": "Клуб «Код»", "org_type": "club", "municipality_id": 1}, headers=headers)
        self.assertEqual(organization.status_code, 201, organization.text)
        self.assertEqual(organization.json()["municipality"]["id"], 1)
        self.assertEqual(self.client.post("/api/v1/reference/organizations", json={"name": "Без района", "org_type": "club", "municipality_id": 999}, headers=headers).status_code, 422)

    def test_regulation_upload_and_download(self) -> None:
        headers = self.admin_headers()
        self.assertEqual(self.client.get("/api/v1/competitions/1/regulation").status_code, 404)
        wrong = self.client.put("/api/v1/competitions/1/regulation", files={"file": ("rules.exe", b"MZ", "application/octet-stream")}, headers=headers)
        self.assertEqual(wrong.status_code, 422)
        uploaded = self.client.put("/api/v1/competitions/1/regulation", files={"file": ("Положение.pdf", b"%PDF-1.4 demo", "application/pdf")}, headers=headers)
        self.assertEqual(uploaded.status_code, 200, uploaded.text)
        self.assertEqual(uploaded.json()["regulation_filename"], "Положение.pdf")
        self.client.cookies.clear()
        downloaded = self.client.get("/api/v1/competitions/1/regulation")
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded.content, b"%PDF-1.4 demo")
        self.assertEqual(downloaded.headers["content-type"], "application/pdf")

    def test_vite_origin_is_allowed(self) -> None:
        response = self.client.options("/api/v1/competitions", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5173")


if __name__ == "__main__":
    unittest.main()
