"""Application settings, read from environment variables.

Defaults mirror `.env.example` at the repo root so the app runs locally with
no `.env` file at all. `DATABASE_URL` is accepted (and validated as a plain
string) even though nothing reads it yet — issue #6 (SQLAlchemy store) needs
the field to already exist here so it doesn't have to touch this file just
to start using it.

`database_url` normalises the bare `postgres://`/`postgresql://` scheme
Render's managed-Postgres `connectionString` returns into
`postgresql+psycopg://`, since `backend/pyproject.toml` only installs
`psycopg[binary]` (psycopg3), not `psycopg2` — SQLAlchemy's default driver
for the bare `postgresql://` scheme. Doing this here, on the Settings field
itself, means every reader of `settings.database_url` (the SQLAlchemy
engine included) gets the corrected URL automatically, with no
Render-specific command-line rewriting needed (see issue #12). A
`sqlite:///...` URL, or a URL that already names a driver (e.g.
`postgresql+psycopg://...`), is left untouched.

`render_git_commit` maps to `RENDER_GIT_COMMIT`, which Render injects
automatically (build time and runtime) with the deployed commit's SHA —
no Blueprint configuration needed (issue #13). It is unset everywhere else
(bare `uv run`/`make run`, Compose, CI's own test jobs), so it defaults to
`None` there; `/health` reports that `None` as-is rather than inventing a
fallback.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./pinpoint.db"
    jwt_secret: str = "local-development-secret-change-me"
    access_token_minutes: int = 60
    cors_origins: str = "http://localhost:5173,http://localhost:8091"
    max_upload_mb: int = 15
    environment: str = "development"
    render_git_commit: str | None = None

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value.removeprefix("postgres://")
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value.removeprefix("postgresql://")
        return value

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
