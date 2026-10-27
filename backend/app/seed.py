"""Idempotent demo seed: reference dictionaries, organizations and competitions. All data is fictional."""

import asyncio
from datetime import date

from sqlalchemy import select

from app.database import SessionFactory
from app.models import (
    AgeGroup, CalendarPlan, Competition, CompetitionFormat, CompetitionLevel, CompetitionStatus,
    CompetitionType, Discipline, Municipality, Organization, OrganizationType,
)
from app.reference_data import seed_reference


ORGANIZATIONS = [
    ("МАОУ «Лицей № 1» г. Оренбурга", OrganizationType.SCHOOL, "г. Оренбург"),
    ("Оренбургский государственный университет", OrganizationType.UNIVERSITY, "г. Оренбург"),
    ("Орский гуманитарно-технологический институт", OrganizationType.UNIVERSITY, "г. Орск"),
    ("Оренбургский колледж информационных технологий", OrganizationType.COLLEGE, "г. Оренбург"),
    ("СШ «Цифровой спорт» г. Новотроицка", OrganizationType.SPORT_SCHOOL, "г. Новотроицк"),
    ("Клуб робототехники «Степные роботы»", OrganizationType.CLUB, "г. Бузулук"),
    ("Центр беспилотных систем «Небо Оренбуржья»", OrganizationType.CLUB, "Оренбургский район"),
]

# (название, код дисциплины, тип, уровень, возрастные группы, даты, место, формат, план, номер, статус, описание)
COMPETITIONS = [
    ("Чемпионат Оренбургской области по алгоритмическому программированию", "algorithmic", "Чемпионат", CompetitionLevel.REGIONAL, [2],
     date(2026, 11, 21), date(2026, 11, 21), date(2026, 10, 20), date(2026, 11, 14), "г. Оренбург, ОГУ, корпус 2", CompetitionFormat.OFFLINE,
     CalendarPlan.REGIONAL, "КП-2026/118", CompetitionStatus.REGISTRATION_OPEN,
     "Личное первенство по решению алгоритмических задач в формате ICPC. Пять часов, 10–12 задач."),
    ("Первенство Оренбургской области по алгоритмическому программированию", "algorithmic", "Первенство", CompetitionLevel.REGIONAL, [0, 1],
     date(2026, 12, 5), date(2026, 12, 5), date(2026, 11, 1), date(2026, 11, 28), "г. Оренбург, Лицей № 1", CompetitionFormat.OFFLINE,
     CalendarPlan.REGIONAL, "КП-2026/119", CompetitionStatus.UPCOMING,
     "Соревнования для школьников по двум возрастным группам."),
    ("Кубок Оренбуржья по продуктовому программированию", "product", "Кубок", CompetitionLevel.REGIONAL, [1, 2],
     date(2026, 12, 12), date(2026, 12, 14), date(2026, 11, 10), date(2026, 12, 5), "Онлайн + защита в г. Оренбурге", CompetitionFormat.MIXED,
     CalendarPlan.REGIONAL, "КП-2026/121", CompetitionStatus.REGISTRATION_OPEN,
     "Командная разработка продукта: два дня онлайн, защита проектов очно."),
    ("Межрегиональные соревнования ПФО по информационной безопасности (CTF)", "security", "Официальные соревнования", CompetitionLevel.INTERREGIONAL, [2],
     date(2026, 11, 28), date(2026, 11, 29), date(2026, 10, 25), date(2026, 11, 20), "Онлайн", CompetitionFormat.ONLINE,
     CalendarPlan.EKP, "ЕКП № 2026-48-0371", CompetitionStatus.REGISTRATION_OPEN,
     "Командные соревнования формата attack-defense для команд Приволжского федерального округа."),
    ("Первенство области по программированию систем ИИ", "ai", "Первенство", CompetitionLevel.REGIONAL, [1],
     date(2026, 10, 10), date(2026, 10, 10), date(2026, 9, 1), date(2026, 10, 3), "Онлайн", CompetitionFormat.ONLINE,
     CalendarPlan.REGIONAL, "КП-2026/097", CompetitionStatus.COMPLETED,
     "Задачи по анализу данных и машинному обучению для юношей и девушек."),
    ("Чемпионат области по программированию робототехники", "robotics", "Чемпионат", CompetitionLevel.REGIONAL, [2],
     date(2027, 2, 14), date(2027, 2, 15), date(2027, 1, 10), date(2027, 2, 7), "г. Бузулук, клуб «Степные роботы»", CompetitionFormat.OFFLINE,
     CalendarPlan.REGIONAL, None, CompetitionStatus.DRAFT,
     "Программирование автономных роботов для прохождения трассы."),
    ("Открытые соревнования по программированию БАС «Степной коптер»", "uav", "Официальные соревнования", CompetitionLevel.REGIONAL, [1, 2],
     date(2027, 3, 21), date(2027, 3, 21), date(2027, 2, 1), date(2027, 3, 14), "Оренбургский район, аэродром «Степь»", CompetitionFormat.OFFLINE,
     CalendarPlan.NONE, None, CompetitionStatus.UPCOMING,
     "Программирование полётных миссий беспилотных авиационных систем."),
]


async def seed() -> None:
    async with SessionFactory() as session:
        await seed_reference(session)

        municipalities = {item.name: item for item in await session.scalars(select(Municipality))}
        existing_orgs = set(await session.scalars(select(Organization.name)))
        for name, org_type, municipality in ORGANIZATIONS:
            if name not in existing_orgs:
                session.add(Organization(name=name, org_type=org_type, municipality=municipalities.get(municipality), is_active=True))

        disciplines = {item.code: item for item in await session.scalars(select(Discipline))}
        types = {item.name: item for item in await session.scalars(select(CompetitionType))}
        age_groups = list(await session.scalars(select(AgeGroup).order_by(AgeGroup.sort_order, AgeGroup.id)))
        existing_titles = set(await session.scalars(select(Competition.title)))
        for (title, code, type_name, level, group_indexes, start, end, reg_start, reg_end, location, event_format,
             plan, plan_number, status, description) in COMPETITIONS:
            if title in existing_titles:
                continue
            session.add(Competition(
                title=title, discipline=disciplines[code], competition_type=types[type_name], level=level,
                age_groups=[age_groups[index] for index in group_indexes if index < len(age_groups)],
                date=start, end_date=end, registration_start=reg_start, registration_end=reg_end,
                location=location, format=event_format, calendar_plan=plan, calendar_plan_number=plan_number,
                status=status, description=description, is_archived=False,
            ))
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
