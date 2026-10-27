import asyncio
import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from sqlalchemy import select

from app.auth_models import Role, User
from app.auth_security import hash_password, login_limiter, utcnow
from app.deadlines import generate_reminders, governor_deadline
from app.notification_models import Notification
from app.notifications import send_pending_emails
from app.qualification_models import AthleteRank, RankNorm, SportRank
from app.qualifications import suggested_rank, validity
from app.models import CompetitionLevel
from support import PASSWORD, ApiDatabase, csrf, register


ADMIN = ("stage2-admin@example.test", "Stage2-Admin-Password-42")
TODAY = date.today()
COMPETITION_DATE = TODAY + timedelta(days=30)


async def seed_admin(session) -> None:
    admin = await session.scalar(select(Role).where(Role.name == "federation_admin"))
    session.add(User(email=ADMIN[0], password_hash=hash_password(ADMIN[1]), created_at=utcnow(), roles=[admin]))


class RulesTests(unittest.TestCase):
    def test_validity(self) -> None:
        self.assertEqual(validity(None), "none")
        self.assertEqual(validity(TODAY - timedelta(days=1)), "expired")
        self.assertEqual(validity(TODAY + timedelta(days=10)), "expiring")
        self.assertEqual(validity(TODAY + timedelta(days=200)), "valid")

    def test_suggested_rank_picks_highest(self) -> None:
        norms = [RankNorm(level=CompetitionLevel.REGIONAL, max_place=3, rank=SportRank.SECOND), RankNorm(level=CompetitionLevel.REGIONAL, max_place=6, rank=SportRank.THIRD)]
        self.assertEqual(suggested_rank(CompetitionLevel.REGIONAL, 2, norms), SportRank.SECOND)
        self.assertEqual(suggested_rank(CompetitionLevel.REGIONAL, 5, norms), SportRank.THIRD)
        self.assertIsNone(suggested_rank(CompetitionLevel.REGIONAL, 9, norms))
        self.assertIsNone(suggested_rank(CompetitionLevel.ALL_RUSSIAN, 1, norms))
        self.assertIsNone(suggested_rank(CompetitionLevel.REGIONAL, None, norms))

    def test_governor_deadline(self) -> None:
        self.assertEqual(governor_deadline(date(2026, 10, 27)), date(2027, 2, 1))
        self.assertEqual(governor_deadline(date(2027, 1, 20)), date(2027, 2, 1))
        self.assertEqual(governor_deadline(date(2027, 2, 2)), date(2028, 2, 1))


class Stage2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.db = ApiDatabase("stage2")
        cls.client = cls.db.prepare(seed_admin)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.db.close(cls.client)

    def setUp(self) -> None:
        self.client.cookies.clear()
        login_limiter.clear()

    # ---------- helpers ----------

    def login(self, email: str, password: str = PASSWORD) -> dict[str, str]:
        self.client.cookies.clear()
        response = self.client.post("/api/v1/auth/login", json={"email": email, "password": password})
        self.assertEqual(response.status_code, 200, response.text)
        return csrf(self.client)

    def admin(self) -> dict[str, str]:
        return self.login(*ADMIN)

    def user_id(self) -> int:
        return self.client.get("/api/v1/auth/me").json()["id"]

    def athlete(self, email: str, last_name: str, age: int = 20, disciplines: list[int] | None = None) -> int:
        self.client.cookies.clear()
        self.assertEqual(register(self.client, email, last_name=last_name).status_code, 201)
        headers = csrf(self.client)
        self.client.put("/api/v1/me/profile", json={"last_name": last_name, "first_name": "Тест", "birth_date": date(COMPETITION_DATE.year - age, 5, 5).isoformat()}, headers=headers)
        self.assertEqual(self.client.put("/api/v1/me/athlete", json={"discipline_ids": disciplines or [1]}, headers=headers).status_code, 200)
        return self.user_id()

    def person(self, email: str, role: str, last_name: str) -> int:
        self.client.cookies.clear()
        self.assertEqual(register(self.client, email, role=role, last_name=last_name).status_code, 201)
        return self.user_id()

    def competition(self, title: str, level: str = "regional") -> int:
        headers = self.admin()
        body = {
            "title": title, "discipline_id": 1, "competition_type_id": 1, "level": level, "age_group_ids": [3],
            "date": COMPETITION_DATE.isoformat(), "end_date": COMPETITION_DATE.isoformat(), "location": "Оренбург", "description": "Тест",
            "format": "offline", "registration_start": (TODAY - timedelta(days=1)).isoformat(), "registration_end": (TODAY + timedelta(days=2)).isoformat(),
            "calendar_plan": "none", "status": "registration_open",
        }
        response = self.client.post("/api/v1/competitions", json=body, headers=headers)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]

    def notifications(self, email: str, password: str = PASSWORD) -> list[dict]:
        self.login(email, password)
        return self.client.get("/api/v1/me/notifications").json()

    # ---------- scenarios ----------

    def test_coach_link_coach_application_and_rank(self) -> None:
        athlete_id = self.athlete("pupil@example.test", "Ученикова")
        coach_id = self.person("coach@example.test", "coach", "Тренеров")
        self.person("other-coach@example.test", "coach", "Чужой")
        competition_id = self.competition("Кубок для тренеров")

        # Тренер находит спортсмена и отправляет запрос.
        headers = self.login("coach@example.test")
        found = self.client.get("/api/v1/coach/athletes/search", params={"q": "Учени"}).json()
        self.assertEqual([item["id"] for item in found], [athlete_id])
        self.assertEqual(found[0]["disciplines"][0]["code"], "algorithmic")
        self.assertEqual(self.client.post("/api/v1/coach/links", json={"athlete_id": athlete_id, "discipline_id": 2}, headers=headers).status_code, 422)
        link = self.client.post("/api/v1/coach/links", json={"athlete_id": athlete_id, "discipline_id": 1}, headers=headers)
        self.assertEqual(link.status_code, 201, link.text)
        link_id = link.json()["id"]
        self.assertEqual(link.json()["status"], "pending")
        self.assertEqual(self.client.post("/api/v1/coach/links", json={"athlete_id": athlete_id, "discipline_id": 1}, headers=headers).status_code, 409)
        # Без подтверждения подать заявку нельзя.
        self.assertEqual(self.client.post(f"/api/v1/competitions/{competition_id}/applications", json={"athlete_id": athlete_id}, headers=headers).status_code, 403)

        # Спортсмен подтверждает.
        headers = self.login("pupil@example.test")
        self.assertIn("link_request", [item["kind"] for item in self.client.get("/api/v1/me/notifications").json()])
        mine = self.client.get("/api/v1/me/coach-links").json()
        self.assertEqual(mine[0]["coach_name"], "Тренеров Тест")
        accepted = self.client.post(f"/api/v1/me/coach-links/{link_id}/respond", json={"accept": True}, headers=headers)
        self.assertEqual(accepted.json()["status"], "active")
        self.assertEqual([event["status"] for event in accepted.json()["history"]], ["pending", "active"])
        self.assertEqual(self.client.post(f"/api/v1/me/coach-links/{link_id}/respond", json={"accept": False}, headers=headers).status_code, 409)

        # Тренер приостанавливает и возобновляет связь — история пишется.
        headers = self.login("coach@example.test")
        self.assertEqual(self.client.post(f"/api/v1/coach/links/{link_id}/status", json={"status": "suspended"}, headers=headers).json()["status"], "suspended")
        self.assertEqual(self.client.post(f"/api/v1/competitions/{competition_id}/applications", json={"athlete_id": athlete_id}, headers=headers).status_code, 403)
        resumed = self.client.post(f"/api/v1/coach/links/{link_id}/status", json={"status": "active", "note": "Вернулся"}, headers=headers)
        self.assertEqual(len(resumed.json()["history"]), 4)

        # Заявка от тренера с проверкой возраста и дисциплины.
        eligibility = self.client.get(f"/api/v1/competitions/{competition_id}/eligibility", params={"athlete_id": athlete_id}).json()
        self.assertTrue(eligibility["eligible"], eligibility)
        applied = self.client.post(f"/api/v1/competitions/{competition_id}/applications", json={"athlete_id": athlete_id}, headers=headers)
        self.assertEqual(applied.status_code, 201, applied.text)
        self.assertEqual(applied.json()["submitted_role"], "coach")
        self.assertEqual(len(self.client.get("/api/v1/coach/applications").json()), 1)

        headers = self.login("other-coach@example.test")
        self.assertEqual(self.client.post(f"/api/v1/competitions/{competition_id}/applications", json={"athlete_id": athlete_id}, headers=headers).status_code, 403)
        self.assertEqual(self.client.get("/api/v1/coach/applications").json(), [])
        self.assertIn("application_by_coach", [item["kind"] for item in self.notifications("pupil@example.test")])

        # Федерация одобряет, вносит результат и публикует протокол.
        headers = self.admin()
        application_id = applied.json()["id"]
        self.client.post(f"/api/v1/applications/{application_id}/decision", json={"status": "approved"}, headers=headers)
        self.client.put(f"/api/v1/competitions/{competition_id}/results", json={"results": [{"application_id": application_id, "score": 100}]}, headers=headers)
        self.assertEqual(self.client.post(f"/api/v1/competitions/{competition_id}/protocol/publish", headers=headers).status_code, 200)

        # Платформа подсвечивает кандидата по ЕВСК: 1 место на региональном — 2 разряд.
        candidates = self.client.get("/api/v1/rank-candidates").json()
        candidate = next(item for item in candidates if item["athlete"]["id"] == athlete_id)
        self.assertEqual(candidate["suggested_rank"], "second")
        self.assertFalse(candidate["pending_request"])

        # Спортсмен с тренером сам заявку на разряд не подаёт — её подаёт тренер.
        headers = self.login("pupil@example.test")
        body = {"rank": "second", "kind": "assign", "application_id": application_id}
        self.assertEqual(self.client.post("/api/v1/rank-requests", json=body, headers=headers).status_code, 409)
        self.assertTrue(self.client.get("/api/v1/me/rank").json()["has_coach"])
        headers = self.login("other-coach@example.test")
        self.assertEqual(self.client.post("/api/v1/rank-requests", json=body | {"athlete_id": athlete_id}, headers=headers).status_code, 403)
        headers = self.login("coach@example.test")
        self.assertEqual(self.client.post("/api/v1/rank-requests", json=body | {"athlete_id": athlete_id, "kind": "confirm"}, headers=headers).status_code, 422)
        request = self.client.post("/api/v1/rank-requests", json=body | {"athlete_id": athlete_id}, headers=headers)
        self.assertEqual(request.status_code, 201, request.text)
        self.assertEqual(request.json()["basis"]["place"], 1)
        self.assertEqual(self.client.post("/api/v1/rank-requests", json=body | {"athlete_id": athlete_id}, headers=headers).status_code, 409)

        # Федерация фиксирует разряд: дата, приказ, срок.
        headers = self.admin()
        request_id = request.json()["id"]
        self.assertTrue(next(item for item in self.client.get("/api/v1/rank-candidates").json() if item["athlete"]["id"] == athlete_id)["pending_request"])
        self.assertEqual(self.client.post(f"/api/v1/rank-requests/{request_id}/decision", json={"status": "approved"}, headers=headers).status_code, 422)
        decision = {"status": "approved", "assigned_on": TODAY.isoformat(), "expires_on": (TODAY + timedelta(days=20)).isoformat(), "order_ref": "Приказ № 12-р"}
        approved = self.client.post(f"/api/v1/rank-requests/{request_id}/decision", json=decision, headers=headers)
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()["current"]["order_ref"], "Приказ № 12-р")
        self.assertNotIn(athlete_id, [item["athlete"]["id"] for item in self.client.get("/api/v1/rank-candidates").json()])
        self.assertIn(athlete_id, [item["athlete"]["id"] for item in self.client.get("/api/v1/ranks/expiring").json()])
        admin_deadlines = self.client.get("/api/v1/me/deadlines").json()
        self.assertIn("rank_expiry", [item["kind"] for item in admin_deadlines])
        self.assertIn("governor", [item["kind"] for item in admin_deadlines])

        # Спортсмен и тренер видят разряд и предупреждение о сроке.
        self.login("pupil@example.test")
        rank = self.client.get("/api/v1/me/rank").json()
        self.assertEqual(rank["current"]["rank"], "second")
        self.assertEqual(rank["current"]["validity"], "expiring")
        deadline = next(item for item in self.client.get("/api/v1/me/deadlines").json() if item["kind"] == "rank_expiry")
        self.assertEqual(deadline["days_left"], 20)
        self.login("coach@example.test")
        summary = self.client.get("/api/v1/coach/athletes").json()
        self.assertEqual(summary[0]["rank"]["rank"], "second")
        self.assertEqual(summary[0]["results"][0]["place"], 1)
        self.assertIn("rank_expiry", [item["kind"] for item in self.client.get("/api/v1/me/deadlines").json()])

        # Напоминания об истечении разряда — спортсмену, тренеру и федерации, без дублей.
        async def run() -> tuple[int, int]:
            async with self.db.session_factory() as session:
                first = await generate_reminders(session)
            async with self.db.session_factory() as session:
                second = await generate_reminders(session)
            return first, second
        first, second = asyncio.run(run())
        self.assertGreaterEqual(first, 3)
        self.assertEqual(second, 0)
        self.assertIn("rank_expiry", [item["kind"] for item in self.notifications("coach@example.test")])
        self.assertIn("rank_expiry", [item["kind"] for item in self.notifications(*ADMIN)])

    def test_athlete_without_coach_requests_rank_and_gets_rejection(self) -> None:
        athlete_id = self.athlete("solo@example.test", "Самостоятельный")
        competition_id = self.competition("Соревнование без тренера")
        headers = self.login("solo@example.test")
        application_id = self.client.post(f"/api/v1/competitions/{competition_id}/applications", headers=headers).json()["id"]
        # Результат ещё не опубликован — основанием быть не может.
        self.assertEqual(self.client.post("/api/v1/rank-requests", json={"rank": "third", "kind": "assign", "application_id": application_id}, headers=headers).status_code, 422)
        headers = self.admin()
        self.client.post(f"/api/v1/applications/{application_id}/decision", json={"status": "approved"}, headers=headers)
        self.client.put(f"/api/v1/competitions/{competition_id}/results", json={"results": [{"application_id": application_id, "score": 10}]}, headers=headers)
        self.client.post(f"/api/v1/competitions/{competition_id}/protocol/publish", headers=headers)
        headers = self.login("solo@example.test")
        created = self.client.post("/api/v1/rank-requests", json={"rank": "third", "kind": "assign", "application_id": application_id}, headers=headers)
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["submitted_role"], "athlete")
        headers = self.admin()
        self.assertEqual(self.client.post(f"/api/v1/rank-requests/{created.json()['id']}/decision", json={"status": "rejected"}, headers=headers).status_code, 422)
        rejected = self.client.post(f"/api/v1/rank-requests/{created.json()['id']}/decision", json={"status": "rejected", "comment": "Нет копии протокола"}, headers=headers)
        self.assertEqual(rejected.json()["status"], "rejected")
        self.login("solo@example.test")
        self.assertIsNone(self.client.get("/api/v1/me/rank").json()["current"])
        self.assertIn("rank_decision", [item["kind"] for item in self.client.get("/api/v1/me/notifications").json()])
        self.assertEqual(athlete_id, self.user_id())

    def test_judges_categories_and_panel(self) -> None:
        judge_id = self.person("judge@example.test", "judge", "Судейкин")
        athlete_id = self.athlete("not-judge@example.test", "Несудья")
        competition_id = self.competition("Соревнование с коллегией")

        headers = self.login("judge@example.test")
        mine = self.client.get("/api/v1/me/judge").json()
        self.assertIsNone(mine["info"]["category"])
        self.assertEqual(self.client.post("/api/v1/me/judge/requests", json={"category": "third", "kind": "confirm", "justification": "Подтверждение категории"}, headers=headers).status_code, 422)
        created = self.client.post("/api/v1/me/judge/requests", json={"category": "third", "kind": "assign", "justification": "Судейство трёх региональных соревнований"}, headers=headers)
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(self.client.post("/api/v1/me/judge/requests", json={"category": "second", "kind": "assign", "justification": "Ещё одна заявка подряд"}, headers=headers).status_code, 409)

        headers = self.admin()
        self.assertIn("judge_request", [item["kind"] for item in self.client.get("/api/v1/me/notifications").json()])
        pending = self.client.get("/api/v1/judge-requests", params={"status": "pending"}).json()
        self.assertEqual([item["judge_id"] for item in pending], [judge_id])
        decision = {"status": "approved", "assigned_on": TODAY.isoformat(), "expires_on": (TODAY + timedelta(days=730)).isoformat(), "order_ref": "Приказ № 5-с"}
        self.assertEqual(self.client.post(f"/api/v1/judge-requests/{created.json()['id']}/decision", json=decision, headers=headers).status_code, 200)
        registry = self.client.get("/api/v1/judges").json()
        self.assertEqual(next(item for item in registry if item["judge_id"] == judge_id)["info"]["category"], "third")

        self.assertEqual(self.client.post(f"/api/v1/competitions/{competition_id}/judges", json={"judge_id": athlete_id, "position_id": 1}, headers=headers).status_code, 422)
        self.assertEqual(self.client.post(f"/api/v1/competitions/{competition_id}/judges", json={"judge_id": judge_id, "position_id": 99}, headers=headers).status_code, 422)
        assigned = self.client.post(f"/api/v1/competitions/{competition_id}/judges", json={"judge_id": judge_id, "position_id": 1}, headers=headers)
        self.assertEqual(assigned.status_code, 201, assigned.text)
        self.assertEqual(assigned.json()["position"]["name"], "Главный судья")
        self.assertEqual(self.client.post(f"/api/v1/competitions/{competition_id}/judges", json={"judge_id": judge_id, "position_id": 2}, headers=headers).status_code, 409)
        self.assertEqual(len(self.client.get(f"/api/v1/competitions/{competition_id}/judges").json()), 1)

        self.login("judge@example.test")
        mine = self.client.get("/api/v1/me/judge").json()
        self.assertEqual(mine["info"]["category"], "third")
        self.assertEqual(mine["info"]["validity"], "valid")
        self.assertEqual(mine["assignments"][0]["competition"]["id"], competition_id)
        kinds = [item["kind"] for item in self.client.get("/api/v1/me/notifications").json()]
        self.assertIn("judge_decision", kinds)
        self.assertIn("judge_assigned", kinds)
        self.assertEqual([item["kind"] for item in self.client.get("/api/v1/me/deadlines").json()], ["category_expiry"])

        headers = self.admin()
        self.assertEqual(self.client.delete(f"/api/v1/competitions/{competition_id}/judges/{assigned.json()['id']}", headers=headers).status_code, 204)
        self.assertEqual(self.client.get(f"/api/v1/competitions/{competition_id}/judges").json(), [])

    def test_notifications_settings_and_email(self) -> None:
        self.athlete("notify@example.test", "Уведомляемый")
        self.competition("Открытие приёма для уведомлений")
        headers = self.login("notify@example.test")
        items = self.client.get("/api/v1/me/notifications").json()
        self.assertIn("registration_open", [item["kind"] for item in items])
        self.assertGreaterEqual(self.client.get("/api/v1/me/notifications/unread-count").json()["unread"], 1)
        self.assertEqual(self.client.post("/api/v1/me/notifications/read", json={"ids": [items[0]["id"]]}, headers=headers).status_code, 200)
        self.assertEqual(self.client.post("/api/v1/me/notifications/read", json={}, headers=headers).json()["unread"], 0)
        self.assertTrue(self.client.get("/api/v1/me/settings").json()["email_notifications"])

        smtp = MagicMock()
        with patch.dict("os.environ", {"SMTP_HOST": "mail.test", "SMTP_PORT": "1025"}), patch("app.notifications.smtplib.SMTP", return_value=smtp) as factory:
            smtp.__enter__.return_value = smtp
            sent = asyncio.run(send_pending_emails(self.db.session_factory))
            again = asyncio.run(send_pending_emails(self.db.session_factory))
        self.assertGreaterEqual(sent, 1)
        self.assertEqual(again, 0)
        factory.assert_called_with("mail.test", 1025, timeout=10)
        recipients = [call.args[0]["To"] for call in smtp.send_message.call_args_list]
        self.assertIn("notify@example.test", recipients)

        # Отключённый email: уведомление остаётся в кабинете, но письмо не уходит.
        self.assertFalse(self.client.put("/api/v1/me/settings", json={"email_notifications": False}, headers=headers).json()["email_notifications"])
        self.competition("Ещё одно открытие приёма")
        smtp.reset_mock()
        with patch.dict("os.environ", {"SMTP_HOST": "mail.test"}), patch("app.notifications.smtplib.SMTP", return_value=smtp):
            smtp.__enter__.return_value = smtp
            asyncio.run(send_pending_emails(self.db.session_factory))
        self.assertNotIn("notify@example.test", [call.args[0]["To"] for call in smtp.send_message.call_args_list])

        async def unsent() -> int:
            async with self.db.session_factory() as session:
                return len(list(await session.scalars(select(Notification).where(Notification.emailed_at.is_(None)))))
        self.assertEqual(asyncio.run(unsent()), 0)

    def test_dashboard_and_permissions(self) -> None:
        self.athlete("dash@example.test", "Дашбордов")
        headers = self.login("dash@example.test")
        for path in ("/api/v1/admin/dashboard", "/api/v1/judges", "/api/v1/rank-requests", "/api/v1/rank-candidates", "/api/v1/coach/links"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.post("/api/v1/admin/reminders/run", headers=headers).status_code, 403)
        self.admin()
        dashboard = self.client.get("/api/v1/admin/dashboard").json()
        self.assertGreaterEqual(dashboard["athletes"], 1)
        self.assertIn("deadlines", dashboard)
        self.assertIn("regional", {item["level"] for item in self.client.get("/api/v1/rank-norms").json()})
        replaced = self.client.put("/api/v1/rank-norms", json=[{"level": "regional", "max_place": 1, "rank": "first"}], headers=csrf(self.client))
        self.assertEqual(replaced.json(), [{"level": "regional", "max_place": 1, "rank": "first"}])
        self.assertEqual(self.client.post("/api/v1/admin/reminders/run", headers=csrf(self.client)).status_code, 200)


if __name__ == "__main__":
    unittest.main()
