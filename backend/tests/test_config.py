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

import pytest
from pydantic import ValidationError

from app.config import DEFAULT_JWT_SECRET, Settings


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


# -- the public default JWT secret must never run in production (issue #26) ----------
# The default is in the public repository (.env.example, docker-compose.yaml).
# render.yaml generates a real JWT_SECRET and sets ENVIRONMENT=production; if
# that were ever missing, the app must refuse to start rather than sign
# tokens with a secret everyone can read.

def test_production_with_default_jwt_secret_refuses_to_start() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(environment="production", jwt_secret=DEFAULT_JWT_SECRET)


def test_production_with_own_jwt_secret_is_accepted() -> None:
    settings = Settings(environment="production", jwt_secret="a-long-random-value-from-the-platform")

    assert settings.jwt_secret == "a-long-random-value-from-the-platform"


def test_development_keeps_working_with_the_default_jwt_secret() -> None:
    settings = Settings(environment="development", jwt_secret=DEFAULT_JWT_SECRET)

    assert settings.jwt_secret == DEFAULT_JWT_SECRET
