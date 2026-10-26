from datetime import date
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


class Competition(BaseModel):
    id: int
    title: str
    discipline: str
    date: date
    location: str
    status: Literal["registration_open", "upcoming", "completed"]


COMPETITIONS = (
    Competition(
        id=1,
        title="Кубок города по программированию",
        discipline="Алгоритмическое программирование",
        date=date(2026, 11, 15),
        location="Оренбург",
        status="registration_open",
    ),
    Competition(
        id=2,
        title="Осенний хакатон",
        discipline="Продуктовое программирование",
        date=date(2026, 11, 28),
        location="Самара",
        status="upcoming",
    ),
    Competition(
        id=3,
        title="Data Science Challenge",
        discipline="Программирование систем искусственного интеллекта",
        date=date(2026, 10, 10),
        location="Онлайн",
        status="completed",
    ),
)

app = FastAPI(title="FSP API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/competitions", response_model=list[Competition])
async def get_competitions() -> tuple[Competition, ...]:
    return COMPETITIONS
