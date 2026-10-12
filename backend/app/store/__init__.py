"""Exposes `Store` (the type routers/auth/tests depend on) and `get_store`
(the FastAPI dependency that resolves it). `InMemoryStore` is constructed
here and nowhere else outside `memory.py` itself — this is the "app wiring"
the issue describes; everyone else gets a `Store` via `Depends(get_store)`.
"""

from __future__ import annotations

from app.store.interface import Store
from app.store.memory import InMemoryStore

_store: Store = InMemoryStore()


def get_store() -> Store:
    return _store


__all__ = ["Store", "get_store"]
