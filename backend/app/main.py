import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.applications import router as applications_router
from app.audit import router as audit_router
from app.auth_routes import router as auth_router
from app.coaching import router as coaching_router
from app.competitions import router as competitions_router
from app.database import SessionFactory
from app.deadlines import background_worker, router as deadlines_router
from app.documents import router as documents_router
from app.effectiveness import router as effectiveness_router
from app.extras import router as extras_router
from app.notifications import router as notifications_router
from app.profile_routes import router as profile_router
from app.qualifications import router as qualifications_router
from app.rating import router as rating_router
from app.reference_routes import router as reference_router
from app.reports import router as reports_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Фоновые напоминания о сроках и отправка email; отключаются BACKGROUND_JOBS=0."""
    stop = asyncio.Event()
    task = None
    if os.getenv("BACKGROUND_JOBS", "1") != "0":
        task = asyncio.create_task(background_worker(SessionFactory, stop))
    yield
    stop.set()
    if task is not None:
        await task


app = FastAPI(title="FSP API", version="0.6.0", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(reference_router)
app.include_router(profile_router)
app.include_router(competitions_router)
app.include_router(applications_router)
app.include_router(coaching_router)
app.include_router(qualifications_router)
app.include_router(deadlines_router)
app.include_router(notifications_router)
app.include_router(rating_router)
app.include_router(reports_router)
app.include_router(documents_router)
app.include_router(audit_router)
app.include_router(extras_router)
app.include_router(effectiveness_router)

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
