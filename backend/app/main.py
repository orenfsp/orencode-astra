from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Competition
from app.schemas import CompetitionRead

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


@app.get("/api/v1/competitions", response_model=list[CompetitionRead])
async def get_competitions(
    session: AsyncSession = Depends(get_session),
) -> list[Competition]:
    result = await session.scalars(select(Competition).order_by(Competition.id))
    return list(result.all())
