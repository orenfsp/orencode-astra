import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.applications import router as applications_router
from app.auth_routes import router as auth_router
from app.competitions import router as competitions_router
from app.profile_routes import router as profile_router
from app.reference_routes import router as reference_router

app = FastAPI(title="FSP API", version="0.2.0")
app.include_router(auth_router)
app.include_router(reference_router)
app.include_router(profile_router)
app.include_router(competitions_router)
app.include_router(applications_router)

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
