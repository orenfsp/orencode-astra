"""Базовые справочники. Миграция 05 содержит собственную копию этих значений."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgeGroup, CompetitionLevel, CompetitionType, Discipline, JudgePosition, Municipality
from app.qualification_models import RankNorm, SportRank


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


# Ориентиры для подсветки кандидатов на разряд (уровень, место не ниже, разряд).
# Федерация сверяет и правит их по действующим нормам ЕВСК через PUT /api/v1/rank-norms.
RANK_NORMS = [
    ("all_russian", 3, "kms"), ("all_russian", 8, "first"), ("all_russian", 16, "second"),
    ("interregional", 3, "first"), ("interregional", 6, "second"), ("interregional", 10, "third"),
    ("regional", 3, "second"), ("regional", 6, "third"), ("regional", 10, "youth_1"),
]


async def seed_rank_norms(session: AsyncSession) -> None:
    if await session.scalar(select(RankNorm.id).limit(1)) is None:
        session.add_all(RankNorm(level=CompetitionLevel(level), max_place=place, rank=SportRank(rank)) for level, place, rank in RANK_NORMS)
        await session.flush()


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
