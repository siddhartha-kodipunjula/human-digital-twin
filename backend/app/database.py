from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from .config import settings

Base = declarative_base()


def _engine_kwargs(url: str) -> dict[str, Any]:
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    if url.startswith("postgresql"):
        # Fail fast when local Postgres is unavailable, then fall back to SQLite.
        return {"pool_pre_ping": True, "connect_args": {"connect_timeout": 3}}
    return {"pool_pre_ping": True}


def _build_engine(url: str) -> Engine:
    return create_engine(url, **_engine_kwargs(url))


def _resolve_engine() -> tuple[Engine, str]:
    primary_url = settings.database_url
    primary_engine = _build_engine(primary_url)
    try:
        with primary_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return primary_engine, primary_url
    except SQLAlchemyError:
        fallback_url = settings.sqlite_fallback_url
        fallback_engine = _build_engine(fallback_url)
        with fallback_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return fallback_engine, fallback_url


engine, ACTIVE_DATABASE_URL = _resolve_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
