"""Application settings, read from environment variables.

Defaults mirror `.env.example` at the repo root so the app runs locally with
no `.env` file at all. `DATABASE_URL` is accepted (and validated as a plain
string) even though nothing reads it yet — issue #6 (SQLAlchemy store) needs
the field to already exist here so it doesn't have to touch this file just
to start using it.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./pinpoint.db"
    jwt_secret: str = "local-development-secret-change-me"
    access_token_minutes: int = 60
    cors_origins: str = "http://localhost:5173,http://localhost:8091"
    max_upload_mb: int = 15
    environment: str = "development"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Module-level instance for the common case (main.py's CORS wiring, auth/'s
# JWT secret/expiry) — `get_settings()` exists for places that prefer a
# FastAPI dependency instead.
settings = get_settings()
