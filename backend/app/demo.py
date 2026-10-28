"""Демо-данные за 2024–2026 годы по всем шести дисциплинам. Все персональные данные вымышлены.

Запуск: python -m app.demo (после миграций и app.seed). Повторный запуск ничего не меняет.
Пароль демо-аккаунтов — переменная DEMO_PASSWORD (по умолчанию Demo-Password-2026).
"""

import asyncio
import os
import random
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.application_models import Application, ApplicationStatus, Result, ResultStatus
from app.auth_models import Role, User
from app.auth_security import hash_password
from app.coaching_models import CoachLink, CoachLinkEvent, LinkStatus
from app.database import SessionFactory
from app.models import (
    AgeGroup, CalendarPlan, Competition, CompetitionFormat, CompetitionLevel, CompetitionStatus, CompetitionType,
    Discipline, JudgePosition, Municipality, Organization, OrganizationType,
)
from app.profile_models import AthleteProfile, CoachProfile, Gender, Profile, TrainingStage
from app.protocol import Entry, competition_age, fitting_groups, rank
from app.qualification_models import (
    AthleteRank, JudgeAssignment, JudgeCategory, JudgeCategoryRequest, JudgeProfile, RankNorm, RankRequest, RequestKind,
    RequestStatus, SportRank,
)
from app.qualifications import suggested_rank
from app.rating import build_rating
from app.rating_models import Sanction, SanctionKind, Team, TeamMember
from app.reference_data import seed_rank_norms, seed_rating, seed_reference


DOMAIN = "demo.fsp56.test"
MARKER = f"federation@{DOMAIN}"
TODAY = date.today()

MALE = ["Александр", "Артём", "Максим", "Дмитрий", "Иван", "Кирилл", "Егор", "Никита", "Михаил", "Тимур", "Даниил", "Роман", "Арсений", "Глеб", "Руслан", "Ильдар"]
FEMALE = ["Анастасия", "Мария", "Дарья", "Полина", "Алина", "Виктория", "Софья", "Екатерина", "Ксения", "Элина", "Варвара", "Камила"]
SURNAMES = [
    ("Смирнов", "Смирнова"), ("Козлов", "Козлова"), ("Морозов", "Морозова"), ("Волков", "Волкова"), ("Соколов", "Соколова"),
    ("Лебедев", "Лебедева"), ("Кузьмин", "Кузьмина"), ("Попов", "Попова"), ("Степанов", "Степанова"), ("Николаев", "Николаева"),
    ("Орлов", "Орлова"), ("Андреев", "Андреева"), ("Макаров", "Макарова"), ("Захаров", "Захарова"), ("Зайцев", "Зайцева"),
    ("Борисов", "Борисова"), ("Яковлев", "Яковлева"), ("Григорьев", "Григорьева"), ("Романов", "Романова"), ("Воробьёв", "Воробьёва"),
    ("Сергеев", "Сергеева"), ("Фролов", "Фролова"), ("Белов", "Белова"), ("Тарасов", "Тарасова"), ("Ахметов", "Ахметова"),
    ("Галиев", "Галиева"), ("Исаев", "Исаева"), ("Мухаметов", "Мухаметова"), ("Ковалёв", "Ковалёва"), ("Ильин", "Ильина"),
]
PATRONYMICS = [("Александрович", "Александровна"), ("Сергеевич", "Сергеевна"), ("Андреевич", "Андреевна"), ("Олегович", "Олеговна"), ("Ринатович", "Ринатовна"), ("Игоревич", "Игоревна")]

EXTRA_ORGANIZATIONS = [
    ("МБОУ «Гимназия № 2» г. Орска", OrganizationType.SCHOOL, "г. Орск"),
    ("Бузулукский колледж промышленности и транспорта", OrganizationType.COLLEGE, "г. Бузулук"),
    ("Центр цифрового образования «IT-куб» г. Оренбурга", OrganizationType.CLUB, "г. Оренбург"),
]

DISCIPLINE_TITLES = {
    "algorithmic": "алгоритмическому программированию", "product": "продуктовому программированию",
    "security": "программированию систем информационной безопасности", "ai": "программированию систем искусственного интеллекта",
    "robotics": "программированию робототехники", "uav": "программированию беспилотных авиационных систем",
}

# (месяц, день, уровень, тип, группы-индексы, место проведения, формат)
SEASON_TEMPLATE = [
    (3, 14, CompetitionLevel.REGIONAL, "Первенство", [0, 1], "г. Оренбург", CompetitionFormat.OFFLINE),
    (5, 23, CompetitionLevel.INTERREGIONAL, "Кубок", [1, 2], "Онлайн", CompetitionFormat.ONLINE),
    (10, 11, CompetitionLevel.REGIONAL, "Чемпионат", [2], "г. Оренбург", CompetitionFormat.MIXED),
]
ALL_RUSSIAN_MONTH = {2024: (11, 16), 2025: (11, 22)}


def at(day: date) -> datetime:
    return datetime.combine(day, time(12, 0), tzinfo=timezone.utc)


def person_name(rng: random.Random, female: bool) -> tuple[str, str, str]:
    surname = rng.choice(SURNAMES)[1 if female else 0]
    first = rng.choice(FEMALE if female else MALE)
    patronymic = rng.choice(PATRONYMICS)[1 if female else 0]
    return surname, first, patronymic


async def load_demo() -> str:
    rng = random.Random(2026)
    async with SessionFactory() as db:
        db.sync_session.info["audit_disabled"] = True  # начальные данные не засоряют журнал действий
        if await db.scalar(select(User.id).where(User.email == MARKER)) is not None:
            return "Демо-данные уже загружены"
        await seed_reference(db)
        await seed_rank_norms(db)
        await seed_rating(db)

        roles = {item.name: item for item in await db.scalars(select(Role))}
        for name in ("athlete", "coach", "judge", "federation_admin"):
            if name not in roles:
                roles[name] = Role(name=name)
                db.add(roles[name])
        municipalities = {item.name: item for item in await db.scalars(select(Municipality))}
        existing_orgs = {item.name for item in await db.scalars(select(Organization))}
        for name, org_type, municipality in EXTRA_ORGANIZATIONS:
            if name not in existing_orgs:
                db.add(Organization(name=name, org_type=org_type, municipality=municipalities[municipality], is_active=True))
        await db.flush()
        organizations = list(await db.scalars(select(Organization).order_by(Organization.id)))
        disciplines = {item.code: item for item in await db.scalars(select(Discipline))}
        types = {item.name: item for item in await db.scalars(select(CompetitionType))}
        groups = list(await db.scalars(select(AgeGroup).order_by(AgeGroup.sort_order, AgeGroup.id)))
        positions = {item.name: item for item in await db.scalars(select(JudgePosition))}
        norms = list(await db.scalars(select(RankNorm)))
        password = hash_password(os.getenv("DEMO_PASSWORD", "Demo-Password-2026"))

        def account(email: str, role_names: list[str], last: str, first: str, middle: str | None, birth: date | None, gender: Gender | None, municipality: Municipality | None, created: date) -> User:
            user = User(email=email, password_hash=password, created_at=at(created), pd_consent_at=at(created), email_notifications=True, roles=[roles[name] for name in role_names])
            db.add(user)
            user.demo_profile = Profile(last_name=last, first_name=first, middle_name=middle, birth_date=birth, gender=gender, municipality=municipality, updated_at=at(created))
            return user

        # ---------- федерация, тренеры, судьи ----------
        federation = account(MARKER, ["federation_admin"], "Федоров", "Олег", "Викторович", date(1984, 6, 2), Gender.MALE, municipalities["г. Оренбург"], date(2024, 1, 10))
        coaches: dict[str, User] = {}
        coach_specs = [
            ("algorithmic", "coach.algo", "Ермаков", "Павел", "Андреевич", False), ("product", "coach.product", "Нестерова", "Ирина", "Олеговна", True),
            ("security", "coach.security", "Хабибуллин", "Артур", "Ринатович", False), ("ai", "coach.ai", "Васильева", "Ольга", "Сергеевна", True),
            ("robotics", "coach.robotics", "Гончаров", "Денис", "Игоревич", False), ("uav", "coach.uav", "Семёнов", "Виктор", "Александрович", False),
        ]
        for code, login, last, first, middle, female in coach_specs:
            coaches[code] = account(f"{login}@{DOMAIN}", ["coach"], last, first, middle, date(rng.randint(1975, 1995), rng.randint(1, 12), rng.randint(1, 28)),
                                    Gender.FEMALE if female else Gender.MALE, municipalities["г. Оренбург"], date(2024, 1, 15))
        # Один аккаунт — две роли: тренер и судья (сценарий С1).
        multi = account(f"coach-judge@{DOMAIN}", ["coach", "judge"], "Литвинова", "Наталья", "Игоревна", date(1988, 9, 14), Gender.FEMALE, municipalities["г. Орск"], date(2024, 2, 1))
        coaches["multi"] = multi
        judges = [multi]
        judge_specs = [
            ("judge.main", "Тимофеев", "Борис", "Сергеевич", JudgeCategory.ALL_RUSSIAN, date(2023, 3, 1), 4),
            ("judge.secretary", "Абрамова", "Елена", "Андреевна", JudgeCategory.FIRST, date(2022, 12, 20), 4),
            ("judge.second", "Калинин", "Роман", "Олегович", JudgeCategory.SECOND, date(2024, 12, 5), 2),
            ("judge.young", "Сафина", "Диана", "Ринатовна", JudgeCategory.THIRD, date(2024, 11, 20), 2),
        ]
        await db.flush()
        for login, last, first, middle, category, assigned, years in judge_specs:
            judge = account(f"{login}@{DOMAIN}", ["judge"], last, first, middle, date(rng.randint(1970, 1998), 4, 4), None, municipalities["г. Оренбург"], date(2024, 1, 20))
            await db.flush()
            db.add(JudgeProfile(user_id=judge.id, category=category, category_assigned_on=assigned,
                                category_expires_on=date(assigned.year + years, assigned.month, assigned.day), order_ref=f"Приказ ФСП № {rng.randint(10, 99)}-с от {assigned:%d.%m.%Y}", updated_at=at(assigned)))
            judges.append(judge)
        db.add(JudgeProfile(user_id=multi.id, category=JudgeCategory.THIRD, category_assigned_on=date(2025, 2, 10), category_expires_on=date(2027, 2, 10),
                            order_ref="Приказ ФСП № 8-с от 10.02.2025", updated_at=at(date(2025, 2, 10))))

        # ---------- спортсмены ----------
        athletes: list[tuple[User, AthleteProfile, int]] = []
        codes = list(disciplines)
        for index in range(72):
            female = rng.random() < 0.38
            last, first, middle = person_name(rng, female)
            birth_year = rng.choice([2009, 2010, 2011, 2012, 2013, 2014, 2015, 2008, 2007, 2006, 2004, 2001, 1999])
            birth = date(birth_year, rng.randint(1, 12), rng.randint(1, 28))
            org = rng.choice(organizations + [None]) if rng.random() < 0.92 else None
            municipality = org.municipality if org is not None and org.municipality else municipalities[rng.choice(list(municipalities))]
            start_year = rng.choice([2021, 2022, 2023, 2023, 2024, 2024, 2025, 2025, 2026])
            created = date(max(start_year, 2024), rng.randint(1, 9), rng.randint(1, 28))
            if created > TODAY:
                created = TODAY - timedelta(days=rng.randint(5, 60))
            user = account(f"athlete{index + 1:02d}@{DOMAIN}", ["athlete"], last, first, middle, birth, Gender.FEMALE if female else Gender.MALE, municipality, created)
            main = codes[index % len(codes)]
            chosen = [disciplines[main]] + ([disciplines[rng.choice(codes)]] if rng.random() < 0.25 else [])
            minor = TODAY.year - birth_year < 18
            stage = TrainingStage.INITIAL if birth_year >= 2013 else TrainingStage.TRAINING if birth_year >= 2008 else rng.choice([TrainingStage.IMPROVEMENT, None])
            profile = AthleteProfile(
                organization=org, start_year=start_year, end_year=rng.choice([2024, 2025]) if rng.random() < 0.08 and start_year <= 2023 else None,
                training_stage=stage, disciplines=list({item.id: item for item in chosen}.values()),
                guardian_name=f"{last} {rng.choice(FEMALE)} {rng.choice(PATRONYMICS)[1]}" if minor else None,
                guardian_phone=f"+7 9{rng.randint(10, 99)} {rng.randint(100, 999)}-{rng.randint(10, 99)}-{rng.randint(10, 99)}" if minor else None,
                guardian_consent_at=at(created) if minor else None,
                rusada_completed_on=created + timedelta(days=rng.randint(3, 40)) if rng.random() < 0.6 else None,
                updated_at=at(created),
            )
            user.demo_athlete = profile
            athletes.append((user, profile, birth_year))
        await db.flush()
        for user in [federation, multi, *coaches.values(), *judges, *(item[0] for item in athletes)]:
            if getattr(user, "demo_profile", None) is not None and user.demo_profile.user_id is None:
                user.demo_profile.user_id = user.id
                db.add(user.demo_profile)
        for user, profile, _birth in athletes:
            profile.user_id = user.id
            db.add(profile)
        for code, coach in coaches.items():
            if code != "multi":
                db.add(CoachProfile(user_id=coach.id, organization=rng.choice(organizations), updated_at=at(date(2024, 1, 15))))
        db.add(CoachProfile(user_id=multi.id, organization=organizations[2], updated_at=at(date(2024, 2, 1))))
        await db.flush()

        # Связи тренер — спортсмен: по основной дисциплине; часть ждёт подтверждения, одна приостановлена.
        coach_of: dict[int, User] = {}
        for index, (user, profile, _birth) in enumerate(athletes):
            code = codes[index % len(codes)]
            coach = coaches["multi"] if code == "algorithmic" and index % 4 == 0 else coaches[code]
            if index % 9 == 8:
                continue  # спортсмен без тренера — сам подаёт заявки на разряд
            status = LinkStatus.PENDING if index % 13 == 5 else LinkStatus.SUSPENDED if index == 17 else LinkStatus.ACTIVE
            since = max(at(user.created_at.date() + timedelta(days=7)), at(date(2024, 2, 1)))
            link = CoachLink(coach_id=coach.id, athlete_id=user.id, discipline_id=disciplines[code].id, status=status, created_at=since, updated_at=since, events=[])
            link.events.append(CoachLinkEvent(status=LinkStatus.PENDING, changed_by_id=coach.id, note="Запрос тренера", created_at=since))
            if status != LinkStatus.PENDING:
                link.events.append(CoachLinkEvent(status=LinkStatus.ACTIVE, changed_by_id=user.id, note="Подтверждено спортсменом", created_at=since + timedelta(days=1)))
            if status == LinkStatus.SUSPENDED:
                link.events.append(CoachLinkEvent(status=LinkStatus.SUSPENDED, changed_by_id=coach.id, note="Академический отпуск", created_at=since + timedelta(days=120)))
            db.add(link)
            if status == LinkStatus.ACTIVE:
                coach_of[user.id] = coach

        # ---------- соревнования с протоколами ----------
        competitions_done = 0
        approved_by_competition: list[tuple[Competition, list[Application]]] = []
        for year in (2024, 2025, 2026):
            schedule = [item for item in SEASON_TEMPLATE]
            for code in codes:
                discipline = disciplines[code]
                plan = list(schedule)
                if year in ALL_RUSSIAN_MONTH and code in {"algorithmic", "security", "ai"}:
                    month, day = ALL_RUSSIAN_MONTH[year]
                    plan.append((month, day, CompetitionLevel.ALL_RUSSIAN, "Чемпионат", [2], "г. Москва (финал)", CompetitionFormat.OFFLINE))
                for month, day, level, type_name, group_indexes, location, fmt in plan:
                    start = date(year, month, min(day + codes.index(code), 28))
                    if start >= TODAY - timedelta(days=3):
                        continue  # будущие соревнования уже есть в базовых данных; демо — только прошедшие
                    if level == CompetitionLevel.ALL_RUSSIAN:
                        title = f"Чемпионат России по {DISCIPLINE_TITLES[code]} {year}"
                    elif level == CompetitionLevel.INTERREGIONAL:
                        title = f"Кубок Приволжского федерального округа по {DISCIPLINE_TITLES[code]} {year}"
                    else:
                        title = f"{type_name} Оренбургской области по {DISCIPLINE_TITLES[code]} {year}"
                    competition = Competition(
                        title=title, discipline=discipline, competition_type=types[type_name], level=level,
                        age_groups=[groups[index] for index in group_indexes], date=start, end_date=start + timedelta(days=1 if fmt == CompetitionFormat.MIXED else 0),
                        location=location, format=fmt, description=f"Официальные соревнования по {DISCIPLINE_TITLES[code]}. Демонстрационные данные.",
                        registration_start=start - timedelta(days=40), registration_end=start - timedelta(days=7),
                        calendar_plan=CalendarPlan.REGIONAL if level == CompetitionLevel.REGIONAL else CalendarPlan.EKP,
                        calendar_plan_number=f"КП-{year}/{rng.randint(10, 199)}" if level == CompetitionLevel.REGIONAL else f"ЕКП № {year}-48-{rng.randint(1000, 9999)}",
                        status=CompetitionStatus.COMPLETED, is_archived=False, protocol_published_at=at(start + timedelta(days=3)),
                    )
                    db.add(competition)
                    await db.flush()
                    eligible = []
                    for user, profile, birth_year in athletes:
                        if discipline not in profile.disciplines:
                            continue
                        if profile.start_year > year or (profile.end_year is not None and profile.end_year < year):
                            continue
                        fitting = fitting_groups(competition_age(date(birth_year, 6, 1), start), competition.age_groups)
                        if fitting:
                            eligible.append((user, fitting[0]))
                    if level == CompetitionLevel.ALL_RUSSIAN:
                        eligible = eligible[:4]  # на всероссийский финал проходят немногие
                    rng.shuffle(eligible)
                    entrants = eligible[: rng.randint(min(5, len(eligible)), min(14, len(eligible)))] if eligible else []
                    applications = []
                    for user, group in entrants:
                        coach = coach_of.get(user.id)
                        application = Application(
                            competition_id=competition.id, athlete_id=user.id, age_group_id=group.id,
                            submitted_by_id=coach.id if coach else user.id, submitted_role="coach" if coach else "athlete",
                            status=ApplicationStatus.APPROVED, created_at=at(competition.registration_start + timedelta(days=rng.randint(1, 30))),
                            decided_at=at(competition.registration_end), decided_by_id=federation.id,
                        )
                        dns = rng.random() < 0.07
                        application.result = Result(result_status=ResultStatus.DNS if dns else ResultStatus.OK,
                                                    score=None if dns else Decimal(rng.randint(120, 980)), updated_at=at(start + timedelta(days=1)))
                        db.add(application)
                        applications.append(application)
                    await db.flush()
                    for group in competition.age_groups:
                        members = [item for item in applications if item.age_group_id == group.id]
                        places = rank([Entry(item.id, item.result.score, item.result.result_status) for item in members])
                        for item in members:
                            item.result.place = places[item.id]
                    for position_name, judge in zip(("Главный судья", "Главный секретарь", "Судья"), rng.sample(judges, 3)):
                        db.add(JudgeAssignment(competition_id=competition.id, judge_id=judge.id, position_id=positions[position_name].id, created_at=at(start - timedelta(days=10))))
                    approved_by_competition.append((competition, applications))
                    competitions_done += 1
        await db.flush()

        # ---------- разряды: присвоены по результатам, часть истекает ----------
        best: dict[int, tuple[SportRank, Application, Competition]] = {}
        for competition, applications in approved_by_competition:
            for application in applications:
                suggested = suggested_rank(competition.level, application.result.place, norms)
                if suggested is None:
                    continue
                previous = best.get(application.athlete_id)
                if previous is None or list(SportRank).index(suggested) > list(SportRank).index(previous[0]):
                    best[application.athlete_id] = (suggested, application, competition)
        ranks_done = pending_done = 0
        for number, (athlete_id, (sport_rank, application, competition)) in enumerate(sorted(best.items())):
            coach = coach_of.get(athlete_id)
            submitter, role = (coach.id, "coach") if coach else (athlete_id, "athlete")
            decided = competition.date + timedelta(days=35)
            if number % 6 == 5 or decided > TODAY:
                db.add(RankRequest(athlete_id=athlete_id, rank=sport_rank, kind=RequestKind.ASSIGN, application_id=application.id, submitted_by_id=submitter,
                                   submitted_role=role, status=RequestStatus.PENDING, created_at=at(min(TODAY, competition.date + timedelta(days=10)))))
                pending_done += 1
                continue
            request = RankRequest(athlete_id=athlete_id, rank=sport_rank, kind=RequestKind.ASSIGN, application_id=application.id, submitted_by_id=submitter,
                                  submitted_role=role, status=RequestStatus.APPROVED, created_at=at(competition.date + timedelta(days=10)),
                                  decided_at=at(decided), decided_by_id=federation.id)
            db.add(request)
            await db.flush()
            years = 3 if sport_rank == SportRank.KMS else 2
            db.add(AthleteRank(athlete_id=athlete_id, rank=sport_rank, assigned_on=decided, expires_on=date(decided.year + years, decided.month, min(decided.day, 28)),
                               order_ref=f"Приказ ФСП № {rng.randint(10, 199)}-р от {decided:%d.%m.%Y}", request_id=request.id, created_at=at(decided)))
            ranks_done += 1
        # Заявка на категорию судьи на рассмотрении.
        db.add(JudgeCategoryRequest(judge_id=judges[4].id, category=JudgeCategory.SECOND, kind=RequestKind.ASSIGN, status=RequestStatus.PENDING,
                                    justification="Судила 5 региональных соревнований в 2025–2026 гг., из них 2 — главным секретарём.", created_at=at(TODAY - timedelta(days=4))))
        # Действующее отстранение — спортсмен выпадает из рейтинга.
        suspended = athletes[11][0]
        db.add(Sanction(athlete_id=suspended.id, kind=SanctionKind.SUSPENSION, starts_on=TODAY - timedelta(days=20), ends_on=TODAY + timedelta(days=160),
                        reason="Решение апелляционной комиссии: нарушение правил командной работы (демо)", created_at=at(TODAY - timedelta(days=20))))
        await db.flush()

        # Сборная по алгоритмическому программированию на 2025 год из рейтинга.
        rating = await build_rating(db, disciplines["algorithmic"].id, 2025)
        if rating.rows:
            team = Team(title="Сборная Оренбургской области по алгоритмическому программированию, 2025", discipline_id=disciplines["algorithmic"].id,
                        season=2025, age_group_id=None, created_at=at(date(2025, 12, 20)))
            team.members = [
                TeamMember(athlete_id=row.athlete.id, position=index, is_reserve=index > 6, rating_place=row.place, rating_points=row.total)
                for index, row in enumerate(rating.rows[:8], start=1)
            ]
            db.add(team)
        await db.commit()
    return (f"Загружено: {len(athletes)} спортсменов, {len(coaches)} тренеров, {len(judges)} судей, {competitions_done} соревнований с протоколами, "
            f"{ranks_done} присвоенных разрядов, {pending_done} заявок на разряд на рассмотрении. Вход: {MARKER}")


if __name__ == "__main__":
    print(asyncio.run(load_demo()))
