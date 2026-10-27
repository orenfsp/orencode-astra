import unittest
from datetime import date

from sqlalchemy import select

from app.models import Organization, OrganizationType
from app.profile_routes import age_on
from support import ApiDatabase, csrf, register


async def seed_organization(session) -> None:
    session.add(Organization(name="Лицей № 1", org_type=OrganizationType.SCHOOL, is_active=True))


def adult_profile(**changes) -> dict:
    body = {"last_name": "Петров", "first_name": "Пётр", "middle_name": "Петрович", "birth_date": "2000-05-17", "gender": "male", "municipality_id": 1, "phone": "+7 900 000-00-00"}
    body.update(changes)
    return body


class ProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.db = ApiDatabase("profile")
        cls.client = cls.db.prepare(seed_organization)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.db.close(cls.client)

    def setUp(self) -> None:
        self.client.cookies.clear()

    def organization_id(self) -> int:
        async def find():
            async with self.db.session_factory() as session:
                return await session.scalar(select(Organization.id))
        import asyncio
        return asyncio.run(find())

    def test_age_is_counted_by_birthday(self) -> None:
        self.assertEqual(age_on(date(2010, 6, 1), date(2026, 5, 31)), 15)
        self.assertEqual(age_on(date(2010, 6, 1), date(2026, 6, 1)), 16)
        self.assertIsNone(age_on(None))

    def test_profile_requires_session_and_csrf(self) -> None:
        self.assertEqual(self.client.get("/api/v1/me/profile").status_code, 401)
        register(self.client, "csrf-profile@example.test")
        self.assertEqual(self.client.put("/api/v1/me/profile", json=adult_profile()).status_code, 403)

    def test_adult_athlete_fills_profile(self) -> None:
        register(self.client, "adult@example.test")
        initial = self.client.get("/api/v1/me/profile").json()
        self.assertEqual(initial["profile"]["last_name"], "Тестов")
        self.assertIsNone(initial["athlete"])
        self.assertIsNotNone(initial["pd_consent_at"])

        athlete_body = {"organization_id": self.organization_id(), "discipline_ids": [1, 4], "start_year": 2019, "training_stage": "training"}
        no_birth_date = self.client.put("/api/v1/me/athlete", json=athlete_body, headers=csrf(self.client))
        self.assertEqual(no_birth_date.status_code, 422)

        saved = self.client.put("/api/v1/me/profile", json=adult_profile(), headers=csrf(self.client))
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["profile"]["municipality"]["name"], "г. Оренбург")
        self.assertFalse(saved.json()["is_minor"])

        athlete = self.client.put("/api/v1/me/athlete", json=athlete_body, headers=csrf(self.client))
        self.assertEqual(athlete.status_code, 200, athlete.text)
        body = athlete.json()["athlete"]
        self.assertEqual([item["code"] for item in body["disciplines"]], ["algorithmic", "ai"])
        self.assertEqual(body["organization"]["name"], "Лицей № 1")

        without_org = self.client.put("/api/v1/me/athlete", json=athlete_body | {"organization_id": None}, headers=csrf(self.client))
        self.assertIsNone(without_org.json()["athlete"]["organization"])

    def test_minor_needs_guardian_consent(self) -> None:
        register(self.client, "minor@example.test")
        self.client.put("/api/v1/me/profile", json=adult_profile(birth_date="2013-03-03"), headers=csrf(self.client))
        athlete_body = {"discipline_ids": [5]}
        self.assertEqual(self.client.put("/api/v1/me/athlete", json=athlete_body, headers=csrf(self.client)).status_code, 422)
        with_guardian = athlete_body | {"guardian_name": "Петрова Мария Ивановна", "guardian_phone": "+7 900 111-11-11"}
        self.assertEqual(self.client.put("/api/v1/me/athlete", json=with_guardian, headers=csrf(self.client)).status_code, 422)
        saved = self.client.put("/api/v1/me/athlete", json=with_guardian | {"guardian_consent": True}, headers=csrf(self.client))
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertTrue(saved.json()["is_minor"])
        self.assertIsNotNone(saved.json()["athlete"]["guardian_consent_at"])

    def test_validation(self) -> None:
        register(self.client, "invalid@example.test")
        headers = csrf(self.client)
        self.assertEqual(self.client.put("/api/v1/me/profile", json=adult_profile(birth_date="2999-01-01"), headers=headers).status_code, 422)
        self.assertEqual(self.client.put("/api/v1/me/profile", json=adult_profile(municipality_id=999), headers=headers).status_code, 422)
        self.assertEqual(self.client.put("/api/v1/me/profile", json=adult_profile(last_name="  "), headers=headers).status_code, 422)
        self.client.put("/api/v1/me/profile", json=adult_profile(), headers=headers)
        self.assertEqual(self.client.put("/api/v1/me/athlete", json={"discipline_ids": [42]}, headers=headers).status_code, 422)
        self.assertEqual(self.client.put("/api/v1/me/athlete", json={"discipline_ids": []}, headers=headers).status_code, 422)
        self.assertEqual(self.client.put("/api/v1/me/athlete", json={"discipline_ids": [1], "organization_id": 999}, headers=headers).status_code, 422)

    def test_role_specific_sections_follow_active_role(self) -> None:
        register(self.client, "coach-athlete@example.test")
        headers = csrf(self.client)
        self.assertEqual(self.client.put("/api/v1/me/coach", json={"organization_id": None}, headers=headers).status_code, 403)
        self.client.post("/api/v1/auth/roles", json={"role": "coach"}, headers=headers)
        coach = self.client.put("/api/v1/me/coach", json={"organization_id": self.organization_id()}, headers=headers)
        self.assertEqual(coach.status_code, 200)
        self.assertEqual(coach.json()["coach"]["organization"]["name"], "Лицей № 1")
        # Активна роль тренера — раздел спортсмена закрыт, пока роль не переключена.
        self.client.put("/api/v1/me/profile", json=adult_profile(), headers=headers)
        self.assertEqual(self.client.put("/api/v1/me/athlete", json={"discipline_ids": [1]}, headers=headers).status_code, 403)


if __name__ == "__main__":
    unittest.main()
