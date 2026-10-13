"""SQLAlchemy-backed `Store` implementation (issue #6).

Submodules:
- `models.py` — ORM models, one table per `store/interface.py` dataclass.
- `engine.py` — engine/session factory built from `settings.database_url`.
- `db_store.py` — `SQLAlchemyStore(Store)`, the concrete store the app wires
  up in `store/__init__.py`.

Nothing outside this package should import SQLAlchemy types directly; other
modules depend on `app.store.interface` dataclasses via `get_store()`.
"""

from __future__ import annotations
