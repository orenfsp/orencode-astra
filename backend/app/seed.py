import asyncio
from datetime import date

from sqlalchemy.dialects.postgresql import insert

from app.database import SessionFactory
from app.models import Competition, CompetitionStatus


COMPETITIONS = [
    {
        "id": 1,
        "title": "Кубок города по программированию",
        "discipline": "Алгоритмическое программирование",
        "date": date(2026, 11, 15),
        "location": "Оренбург",
        "status": CompetitionStatus.REGISTRATION_OPEN,
    },
    {
        "id": 2,
        "title": "Осенний хакатон",
        "discipline": "Продуктовое программирование",
        "date": date(2026, 11, 28),
        "location": "Самара",
        "status": CompetitionStatus.UPCOMING,
    },
    {
        "id": 3,
        "title": "Data Science Challenge",
        "discipline": "Программирование систем искусственного интеллекта",
        "date": date(2026, 10, 10),
        "location": "Онлайн",
        "status": CompetitionStatus.COMPLETED,
    },
]


async def seed() -> None:
    async with SessionFactory() as session:
        statement = insert(Competition).values(COMPETITIONS)
        await session.execute(statement.on_conflict_do_nothing(index_elements=["id"]))
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
