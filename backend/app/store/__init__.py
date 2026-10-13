"""Exposes `Store` (the type routers/auth/tests depend on) and `get_store`
(the FastAPI dependency that resolves it). `SQLAlchemyStore` is constructed
here and nowhere else outside `store/sqlalchemy/` itself — this is the "app
wiring" the issue describes; everyone else gets a `Store` via
`Depends(get_store)`.

Backed by `settings.database_url` (SQLite locally by default, Postgres when
`DATABASE_URL` points at one) — this is what makes room/image/pin/comment
data survive a backend restart (issue #6).
"""

from __future__ import annotations

from app.config import settings
from app.store.interface import Store
from app.store.sqlalchemy.db_store import SQLAlchemyStore

_store: Store = SQLAlchemyStore(settings.database_url)


def get_store() -> Store:
    return _store


__all__ = ["Store", "get_store"]
