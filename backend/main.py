from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

if __package__:
    from .app.config import settings
    from .app.database import ACTIVE_DATABASE_URL, init_database
    from .app.routers import auth, daily_logs, dashboard, ml_ops, nutrition, predictions, profile
else:  # pragma: no cover
    from app.config import settings  # type: ignore
    from app.database import ACTIVE_DATABASE_URL, init_database  # type: ignore
    from app.routers import auth, daily_logs, dashboard, ml_ops, nutrition, predictions, profile  # type: ignore

app = FastAPI(
    title=settings.app_name,
    version="2.0.0",
    description=(
        "Production-style Human Digital Twin platform with JWT auth, profile-aware ML predictions, "
        "time-series forecasting, scenario simulation, analytics, and nutrition intelligence."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
app.mount("/artifacts", StaticFiles(directory=settings.artifacts_dir), name="artifacts")

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(profile.router, prefix=settings.api_prefix)
app.include_router(daily_logs.router, prefix=settings.api_prefix)
app.include_router(nutrition.router, prefix=settings.api_prefix)
app.include_router(predictions.router, prefix=settings.api_prefix)
app.include_router(dashboard.router, prefix=settings.api_prefix)
app.include_router(ml_ops.router, prefix=settings.api_prefix)


@app.on_event("startup")
def on_startup() -> None:
    init_database()


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": settings.app_name,
        "version": "2.0.0",
        "docs": "/docs",
        "api_prefix": settings.api_prefix,
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database_url_in_use": ACTIVE_DATABASE_URL,
    }
