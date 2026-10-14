"""Unit tests for Settings.database_url's dialect normalisation.

See issue #12's reopening comment: a bare postgres:// or postgresql:// URL
(what Render's managed-Postgres connectionString returns) must be rewritten
to postgresql+psycopg://, since backend/pyproject.toml only installs
psycopg[binary] (psycopg3), not psycopg2 — SQLAlchemy's default driver for
the bare postgresql:// scheme. sqlite:///... and already-qualified
postgresql+psycopg://... URLs must pass through untouched.

These construct Settings directly rather than going through the module-level
`settings` singleton, so they don't depend on (or disturb) the DATABASE_URL
env var conftest.py pins for the rest of the suite.
"""

from __future__ import annotations

from app.config import Settings


def test_bare_postgresql_scheme_is_normalized() -> None:
    settings = Settings(database_url="postgresql://pinpoint:pass@dpg-abc123/pinpoint")

    assert settings.database_url == "postgresql+psycopg://pinpoint:pass@dpg-abc123/pinpoint"


def test_bare_postgres_scheme_is_normalized() -> None:
    settings = Settings(database_url="postgres://pinpoint:pass@dpg-abc123/pinpoint")

    assert settings.database_url == "postgresql+psycopg://pinpoint:pass@dpg-abc123/pinpoint"


def test_sqlite_url_is_left_untouched() -> None:
    settings = Settings(database_url="sqlite:///./pinpoint.db")

    assert settings.database_url == "sqlite:///./pinpoint.db"


def test_already_qualified_psycopg_url_is_idempotent() -> None:
    settings = Settings(database_url="postgresql+psycopg://pinpoint:pass@dpg-abc123/pinpoint")

    assert settings.database_url == "postgresql+psycopg://pinpoint:pass@dpg-abc123/pinpoint"
