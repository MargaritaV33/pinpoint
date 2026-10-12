"""Shared test fixtures.

`client` resets the store to its freshly-seeded state before each test via
`Store.reset()` (part of the `Store` interface itself), so tests never
import `InMemoryStore` directly — only `get_store`, which returns the
`Store`-typed singleton the app already uses.
"""

from __future__ import annotations

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
