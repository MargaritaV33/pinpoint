"""Builds the synchronous SQLAlchemy `Engine` and session factory this
project uses. Plain `sqlalchemy` only — no `asyncio`/`asyncpg`/`aiosqlite`;
every route in this backend is a sync `def`, so a sync engine is the whole
solution (see issue #6).

For a SQLite URL (always `:memory:` in this project's test suite, and
file-based for local dev) we pass `poolclass=StaticPool` and
`connect_args={"check_same_thread": False}` so the one logical database
survives across the different connections FastAPI's threadpool opens — this
matters most for `sqlite:///:memory:`, where a plain pool would hand out a
fresh, empty database per connection. A `postgresql://` URL uses SQLAlchemy's
normal pooling untouched.
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def build_engine(database_url: str) -> Engine:
    if database_url.startswith("sqlite"):
        return create_engine(
            database_url,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
    return create_engine(database_url)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
