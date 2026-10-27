import unittest
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import select

from app.application_models import ResultStatus
from app.auth_models import Role, User
from app.auth_security import hash_password, login_limiter, utcnow
from app.protocol import Entry, competition_age, fitting_groups, rank
from support import ApiDatabase, csrf, register


ADMIN = ("protocol-admin@example.test", "Protocol-Admin-Password-42")
TODAY = date.today()
COMPETITION_DATE = TODAY + timedelta(days=30)


async def seed_admin(session) -> None:
    admin = await session.scalar(select(Role).where(Role.name == "federation_admin"))
    session.add(User(email=ADMIN[0], password_hash=hash_password(ADMIN[1]), created_at=utcnow(), roles=[admin]))


def birth_for_age(age: int) -> str:
    """Дата рождения, при которой в год соревнования спортсмену исполняется age лет."""
    return date(COMPETITION_DATE.year - age, 3, 15).isoformat()


class RulesTests(unittest.TestCase):
    def test_age_is_counted_by_birth_year(self) -> None:
        self.assertEqual(competition_age(date(2012, 12, 31), date(2026, 1, 10)), 14)
        self.assertEqual(competition_age(date(2012, 1, 1), date(2026, 12, 31)), 14)

    def test_fitting_groups(self) -> None:
        groups = [SimpleNamespace(id=1, min_age=10, max_age=13), SimpleNamespace(id=2, min_age=14, max_age=17), SimpleNamespace(id=3, min_age=16, max_age=None)]
        self.assertEqual([group.id for group in fitting_groups(12, groups)], [1])
        self.assertEqual([group.id for group in fitting_groups(16, groups)], [2, 3])
        self.assertEqual([group.id for group in fitting_groups(40, groups)], [3])
        self.assertEqual(fitting_groups(8, groups), [])

    def test_rank_shares_places_and_skips_non_ranked(self) -> None:
        places = rank([
            Entry(1, Decimal("80"), ResultStatus.OK),
            Entry(2, Decimal("95.5"), ResultStatus.OK),
            Entry(3, Decimal("80"), ResultStatus.OK),
            Entry(4, Decimal("10"), ResultStatus.OK),
            Entry(5, None, ResultStatus.DNS),
            Entry(6, None, ResultStatus.DSQ),
        ])
        self.assertEqual(places, {2: 1, 1: 2, 3: 2, 4: 4, 5: None, 6: None})


class ApplicationFlowTests(unittest.TestCase):
    """Сквозной сценарий: соревнование → заявки → модерация → результаты → протокол → история."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.db = ApiDatabase("applications")
        cls.client = cls.db.prepare(seed_admin)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.db.close(cls.client)

    def setUp(self) -> None:
        self.client.cookies.clear()
        login_limiter.clear()

    def login_admin(self) -> dict[str, str]:
        self.client.cookies.clear()
        response = self.client.post("/api/v1/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]})
        self.assertEqual(response.status_code, 200)
        return csrf(self.client)

    def login(self, email: str) -> dict[str, str]:
        self.client.cookies.clear()
        self.assertEqual(self.client.post("/api/v1/auth/login", json={"email": email, "password": "Correct-Horse-42"}).status_code, 200)
        return csrf(self.client)

    def athlete(self, email: str, last_name: str, age: int, disciplines: list[int]) -> None:
        self.client.cookies.clear()
        self.assertEqual(register(self.client, email, last_name=last_name).status_code, 201)
        headers = csrf(self.client)
        self.assertEqual(self.client.put("/api/v1/me/profile", json={"last_name": last_name, "first_name": "Тест", "birth_date": birth_for_age(age), "municipality_id": 1}, headers=headers).status_code, 200)
        body = {"discipline_ids": disciplines}
        if age < 18:
            body |= {"guardian_name": "Законный Представитель", "guardian_phone": "+7 900 000-00-00", "guardian_consent": True}
        self.assertEqual(self.client.put("/api/v1/me/athlete", json=body, headers=headers).status_code, 200)

    def create_competition(self, headers: dict[str, str], **changes) -> int:
        body = {
            "title": "Первенство области", "discipline_id": 1, "competition_type_id": 2, "level": "regional", "age_group_ids": [2],
            "date": COMPETITION_DATE.isoformat(), "end_date": COMPETITION_DATE.isoformat(), "location": "Оренбург",
            "description": "Тест", "format": "offline", "registration_start": (TODAY - timedelta(days=1)).isoformat(),
            "registration_end": (TODAY + timedelta(days=10)).isoformat(), "calendar_plan": "regional", "status": "registration_open",
        }
        body.update(changes)
        response = self.client.post("/api/v1/competitions", json=body, headers=headers)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]

    def apply(self, email: str, competition_id: int):
        headers = self.login(email)
        return self.client.post(f"/api/v1/competitions/{competition_id}/applications", headers=headers)

    def test_end_to_end_protocol(self) -> None:
        admin = self.login_admin()
        competition_id = self.create_competition(admin)
        draft_id = self.create_competition(admin, title="Ещё не открыто", status="upcoming")

        self.athlete("a1@example.test", "Альфа", 15, [1])
        self.athlete("a2@example.test", "Бета", 16, [1, 2])
        self.athlete("a3@example.test", "Гамма", 17, [1])
        self.athlete("a4@example.test", "Дельта", 14, [1])
        self.athlete("wrong-discipline@example.test", "Ошибка", 15, [2])
        self.athlete("too-young@example.test", "Малыш", 11, [1])

        # Проверка допуска и подача заявки.
        self.login("a1@example.test")
        eligibility = self.client.get(f"/api/v1/competitions/{competition_id}/eligibility").json()
        self.assertTrue(eligibility["eligible"], eligibility)
        self.assertEqual(eligibility["age"], 15)
        self.assertEqual(eligibility["age_group"]["id"], 2)

        first = self.apply("a1@example.test", competition_id)
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(first.json()["status"], "pending")
        self.assertEqual(self.apply("a1@example.test", competition_id).status_code, 409)
        closed = self.apply("a1@example.test", draft_id)
        self.assertEqual(closed.status_code, 422)
        self.assertIn("не открыт", closed.json()["detail"])

        wrong = self.apply("wrong-discipline@example.test", competition_id)
        self.assertEqual(wrong.status_code, 422)
        self.assertIn("дисциплина", wrong.json()["detail"])
        young = self.apply("too-young@example.test", competition_id)
        self.assertEqual(young.status_code, 422)
        self.assertIn("Возраст в год соревнования — 11", young.json()["detail"])

        ids = {"a1": first.json()["id"]}
        for key in ("a2", "a3", "a4"):
            response = self.apply(f"{key}@example.test", competition_id)
            self.assertEqual(response.status_code, 201, response.text)
            ids[key] = response.json()["id"]

        # a4 отзывает заявку и подаёт повторно.
        headers = self.login("a4@example.test")
        self.assertEqual(self.client.post(f"/api/v1/applications/{ids['a4']}/withdraw", headers=headers).json()["status"], "withdrawn")
        self.assertEqual(self.apply("a4@example.test", competition_id).json()["status"], "pending")
        self.assertEqual(len(self.client.get("/api/v1/me/applications").json()), 1)

        # Модерация федерацией.
        admin = self.login_admin()
        listed = self.client.get(f"/api/v1/competitions/{competition_id}/applications").json()
        self.assertEqual(len(listed), 4)
        self.assertEqual(listed[0]["athlete"]["municipality"], "г. Оренбург")
        self.assertEqual(self.client.post(f"/api/v1/applications/{ids['a4']}/decision", json={"status": "rejected"}, headers=admin).status_code, 422)
        rejected = self.client.post(f"/api/v1/applications/{ids['a4']}/decision", json={"status": "rejected", "comment": "Нет справки"}, headers=admin)
        self.assertEqual(rejected.json()["moderator_comment"], "Нет справки")
        for key in ("a1", "a2", "a3"):
            self.assertEqual(self.client.post(f"/api/v1/applications/{ids[key]}/decision", json={"status": "approved"}, headers=admin).status_code, 200)
        self.assertEqual(self.client.post(f"/api/v1/applications/{ids['a1']}/decision", json={"status": "rejected", "comment": "x"}, headers=admin).status_code, 409)

        # Протокол до публикации: виден федерации, скрыт от остальных; без результатов он неполный.
        protocol = self.client.get(f"/api/v1/competitions/{competition_id}/protocol").json()
        self.assertFalse(protocol["is_complete"])
        self.assertEqual(len(protocol["groups"][0]["rows"]), 3)
        self.assertEqual(self.client.post(f"/api/v1/competitions/{competition_id}/protocol/publish", headers=admin).status_code, 409)
        self.assertEqual(self.client.put(f"/api/v1/competitions/{competition_id}/results", json={"results": [{"application_id": ids["a4"], "score": 10}]}, headers=admin).status_code, 422)

        saved = self.client.put(f"/api/v1/competitions/{competition_id}/results", json={"results": [
            {"application_id": ids["a1"], "score": "250.5"},
            {"application_id": ids["a2"], "score": "250.5"},
            {"application_id": ids["a3"], "result_status": "dns"},
        ]}, headers=admin)
        self.assertEqual(saved.status_code, 200, saved.text)
        rows = saved.json()["groups"][0]["rows"]
        self.assertEqual([(row["athlete"]["full_name"].split()[0], row["place"]) for row in rows], [("Альфа", 1), ("Бета", 1), ("Гамма", None)])
        self.assertTrue(saved.json()["is_complete"])

        # Исправление результата пересчитывает места.
        fixed = self.client.put(f"/api/v1/competitions/{competition_id}/results", json={"results": [{"application_id": ids["a2"], "score": "300"}]}, headers=admin)
        self.assertEqual([row["place"] for row in fixed.json()["groups"][0]["rows"]], [1, 2, None])

        self.client.cookies.clear()
        self.assertEqual(self.client.get(f"/api/v1/competitions/{competition_id}/protocol").status_code, 404)

        admin = self.login_admin()
        published = self.client.post(f"/api/v1/competitions/{competition_id}/protocol/publish", headers=admin)
        self.assertEqual(published.status_code, 200)
        self.assertIsNotNone(published.json()["published_at"])
        self.assertEqual(self.client.get(f"/api/v1/competitions/{competition_id}").json()["status"], "completed")
        self.assertEqual(self.client.put(f"/api/v1/competitions/{competition_id}/results", json={"results": [{"application_id": ids["a1"], "score": 1}]}, headers=admin).status_code, 409)

        # Публичный протокол и история выступлений спортсмена.
        self.client.cookies.clear()
        self.assertEqual(self.client.get(f"/api/v1/competitions/{competition_id}/protocol").status_code, 200)
        self.login("a1@example.test")
        history = self.client.get("/api/v1/me/results").json()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["place"], 2)
        self.assertEqual(history[0]["participants"], 3)
        self.assertEqual(history[0]["competition"]["level"], "regional")
        self.login("a4@example.test")
        self.assertEqual(self.client.get("/api/v1/me/results").json(), [])

    def test_permissions(self) -> None:
        admin = self.login_admin()
        competition_id = self.create_competition(admin, title="Права доступа")
        self.athlete("perm@example.test", "Права", 16, [1])
        headers = csrf(self.client)
        self.assertEqual(self.client.get(f"/api/v1/competitions/{competition_id}/applications").status_code, 403)
        self.assertEqual(self.client.put(f"/api/v1/competitions/{competition_id}/results", json={"results": [{"application_id": 1, "score": 1}]}, headers=headers).status_code, 403)
        self.assertEqual(self.client.post(f"/api/v1/competitions/{competition_id}/applications").status_code, 403)

        # Из кабинета тренера заявку подают только за привязанного спортсмена.
        self.client.post("/api/v1/auth/roles", json={"role": "coach"}, headers=headers)
        self.assertEqual(self.client.post(f"/api/v1/competitions/{competition_id}/applications", headers=headers).status_code, 422)
        self.assertEqual(self.client.post(f"/api/v1/competitions/{competition_id}/applications", json={"athlete_id": 1}, headers=headers).status_code, 403)
        self.assertFalse(self.client.get(f"/api/v1/competitions/{competition_id}/eligibility").json()["eligible"])

        self.client.cookies.clear()
        self.assertEqual(self.client.get(f"/api/v1/competitions/{competition_id}/eligibility").status_code, 401)

    def test_score_validation(self) -> None:
        admin = self.login_admin()
        competition_id = self.create_competition(admin, title="Валидация баллов")
        for body in ({"results": []}, {"results": [{"application_id": 1}]}, {"results": [{"application_id": 1, "score": -1}]}):
            with self.subTest(body=body):
                self.assertEqual(self.client.put(f"/api/v1/competitions/{competition_id}/results", json=body, headers=admin).status_code, 422)


if __name__ == "__main__":
    unittest.main()
