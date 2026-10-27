"""Базовые справочники. Миграция 05 содержит собственную копию этих значений."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgeGroup, CompetitionType, Discipline, JudgePosition, Municipality


DISCIPLINES = [
    ("algorithmic", "Программирование алгоритмическое"),
    ("product", "Программирование продуктовое"),
    ("security", "Программирование систем информационной безопасности"),
    ("ai", "Программирование систем искусственного интеллекта"),
    ("robotics", "Программирование робототехники"),
    ("uav", "Программирование беспилотных авиационных систем"),
]

COMPETITION_TYPES = ["Чемпионат", "Первенство", "Кубок", "Всероссийские соревнования", "Официальные соревнования"]

# Значения редактируются федерацией; проверяются по правилам вида спорта (приказ № 584).
AGE_GROUPS = [
    ("Мальчики, девочки (10–13 лет)", 10, 13),
    ("Юноши, девушки (14–17 лет)", 14, 17),
    ("Мужчины, женщины (16 лет и старше)", 16, None),
]

MUNICIPALITIES = [
    "г. Оренбург", "г. Орск", "г. Новотроицк", "г. Бузулук", "г. Бугуруслан", "г. Медногорск",
    "Гайский городской округ", "Сорочинский городской округ", "Кувандыкский городской округ",
    "Соль-Илецкий городской округ", "Ясненский городской округ", "Абдулинский городской округ",
    "Оренбургский район", "Бузулукский район", "Саракташский район", "Новосергиевский район",
]

JUDGE_POSITIONS = [
    "Главный судья", "Заместитель главного судьи", "Главный секретарь",
    "Заместитель главного секретаря", "Судья", "Технический специалист",
]


async def seed_reference(session: AsyncSession) -> None:
    """Idempotently insert the reference dictionaries (used by tests and the demo seed)."""

    async def existing(column) -> set[str]:
        return set(await session.scalars(select(column)))

    codes = await existing(Discipline.code)
    for index, (code, name) in enumerate(DISCIPLINES):
        if code not in codes:
            session.add(Discipline(code=code, name=name, sort_order=index))
    types = await existing(CompetitionType.name)
    session.add_all(CompetitionType(name=name, is_active=True) for name in COMPETITION_TYPES if name not in types)
    groups = await existing(AgeGroup.name)
    for index, (name, min_age, max_age) in enumerate(AGE_GROUPS):
        if name not in groups:
            session.add(AgeGroup(name=name, min_age=min_age, max_age=max_age, sort_order=index))
    municipalities = await existing(Municipality.name)
    session.add_all(Municipality(name=name) for name in MUNICIPALITIES if name not in municipalities)
    positions = await existing(JudgePosition.name)
    session.add_all(JudgePosition(name=name) for name in JUDGE_POSITIONS if name not in positions)
    await session.flush()
