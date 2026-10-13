"""Shared test fixtures.

Before anything imports `app.main` (which builds the `SQLAlchemyStore`
singleton from `settings.database_url` at import time), this module pins
`DATABASE_URL` for the whole test run:

- If `TEST_DATABASE_URL` is set in the environment (expected to be a
  reachable `postgresql://` URL), it becomes `DATABASE_URL` and the entire
  suite runs against that Postgres instance.
- Otherwise `DATABASE_URL` is forced to a dedicated `sqlite:///:memory:`
  database (kept alive across connections by the `StaticPool` engine in
  `app.store.sqlalchemy.engine`), distinct from a developer's local
  `pinpoint.db` file, so `make test` never reads or clobbers it.

There is no third, partially-skipped state — the suite runs fully against
one database or the other.

`client` resets the store to its freshly-seeded state before each test via
`Store.reset()` (part of the `Store` interface itself), so tests never
import `SQLAlchemyStore`/`InMemoryStore` directly — only `get_store`, which
returns the `Store`-typed singleton the app already uses.
"""

from __future__ import annotations

import os

if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
else:
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store import get_store


@pytest.fixture()
def client() -> TestClient:
    get_store().reset()
    return TestClient(app)


@pytest.fixture()
def studio_token(client: TestClient) -> str:
    response = client.post("/auth/login", json={"email": "demo@pinpoint.studio", "password": "pinpoint"})
    assert response.status_code == 200
    return response.json()["token"]


@pytest.fixture()
def auth_headers(studio_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {studio_token}"}
