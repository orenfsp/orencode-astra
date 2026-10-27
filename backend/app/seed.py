import asyncio
from datetime import date

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import text

from app.database import SessionFactory
from app.models import Competition, CompetitionStatus


COMPETITIONS = [
    {
        "id": 1,
        "title": "Кубок города по программированию",
        "discipline": "Алгоритмическое программирование",
        "date": date(2026, 11, 15),
        "location": "Оренбург",
        "description": "Региональный турнир для школьников и студентов с задачами по алгоритмам и структурам данных.",
        "event_format": "Очно",
        "registration_start": date(2026, 10, 15),
        "registration_end": date(2026, 11, 10),
        "is_archived": False,
        "status": CompetitionStatus.REGISTRATION_OPEN,
    },
    {
        "id": 2,
        "title": "Осенний хакатон",
        "discipline": "Продуктовое программирование",
        "date": date(2026, 11, 28),
        "location": "Самара",
        "description": "Командная разработка цифрового продукта по задаче от индустриального партнёра.",
        "event_format": "Гибридный",
        "registration_start": date(2026, 10, 20),
        "registration_end": date(2026, 11, 20),
        "is_archived": False,
        "status": CompetitionStatus.UPCOMING,
    },
    {
        "id": 3,
        "title": "Data Science Challenge",
        "discipline": "Программирование систем искусственного интеллекта",
        "date": date(2026, 10, 10),
        "location": "Онлайн",
        "description": "Соревнование по анализу данных и построению моделей машинного обучения.",
        "event_format": "Онлайн",
        "registration_start": date(2026, 9, 1),
        "registration_end": date(2026, 10, 5),
        "is_archived": False,
        "status": CompetitionStatus.COMPLETED,
    },
]


async def seed() -> None:
    async with SessionFactory() as session:
        statement = insert(Competition).values(COMPETITIONS)
        await session.execute(statement.on_conflict_do_nothing(index_elements=["id"]))
        if session.get_bind().dialect.name == "postgresql":
            await session.execute(
                text(
                    "SELECT setval(pg_get_serial_sequence('competitions', 'id'), "
                    "COALESCE(MAX(id), 1), true) FROM competitions"
                )
            )
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
