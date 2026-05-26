from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _split_csv_env(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    values = [item.strip() for item in raw.split(",")]
    return [item for item in values if item]


@dataclass(frozen=True)
class Settings:
    project_root: Path = Path(__file__).resolve().parents[2]
    app_name: str = "Human Digital Twin AI Platform"
    api_prefix: str = "/api/v1"
    secret_key: str = os.getenv("JWT_SECRET_KEY", "change-me-for-production")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "120"))
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/human_digital_twin",
    )
    cors_origins: list[str] = None  # type: ignore[assignment]
    models_dir: Path = None  # type: ignore[assignment]
    artifacts_dir: Path = None  # type: ignore[assignment]
    dataset_path: Path = None  # type: ignore[assignment]
    sqlite_fallback_url: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "cors_origins", _split_csv_env("CORS_ORIGINS", "*"))
        models_dir = self.project_root / "models"
        artifacts_dir = self.project_root / "backend" / "artifacts"
        dataset_path = self.project_root / "dataset" / "wellness_dataset.csv"
        sqlite_fallback = f"sqlite:///{(self.project_root / 'backend' / 'wellness_platform.db').as_posix()}"
        object.__setattr__(self, "models_dir", models_dir)
        object.__setattr__(self, "artifacts_dir", artifacts_dir)
        object.__setattr__(self, "dataset_path", dataset_path)
        object.__setattr__(self, "sqlite_fallback_url", sqlite_fallback)


settings = Settings()
