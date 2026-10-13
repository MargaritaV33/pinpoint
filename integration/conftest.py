"""Shared fixtures and HTTP helpers for the integration suite.

Every test in `tests/` drives an already-running Docker Compose stack over
real HTTP — nothing here imports from `backend/`. The stack's base URL is
`PINPOINT_BASE_URL` (default `http://localhost:8100`, matching
`docker-compose.yaml`'s `APP_PORT:-8100`).

A short, explicit client timeout (5 seconds) means a stack that isn't up
fails fast with a readable connection-refused error instead of hanging.
"""

from __future__ import annotations

import os
from uuid import uuid4

import httpx
import pytest

DEFAULT_BASE_URL = "http://localhost:8100"
REQUEST_TIMEOUT_SECONDS = 5.0


@pytest.fixture
def base_url() -> str:
    return os.environ.get("PINPOINT_BASE_URL", DEFAULT_BASE_URL)


@pytest.fixture
def client(base_url: str):
    with httpx.Client(base_url=base_url, timeout=REQUEST_TIMEOUT_SECONDS) as c:
        yield c


# --- HTTP helpers --------------------------------------------------------
#
# Plain functions, not fixtures: every scenario test needs a different mix
# of studio users, rooms, and guest actions, so a helper per HTTP call
# keeps each test's setup readable while still creating its own data
# in-test (no shared fixture state, no reliance on seed data).


def unique_email() -> str:
    return f"it-{uuid4()}@example.com"


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def signup(client: httpx.Client, *, email: str | None = None, password: str = "testpass123") -> httpx.Response:
    return client.post(
        "/auth/signup",
        json={"email": email or unique_email(), "password": password},
    )


def create_studio(client: httpx.Client, *, password: str = "testpass123") -> dict:
    """Signs up a brand-new studio user and returns its session dict
    (`token` and `user`, same shape as the `Session` schema)."""
    response = signup(client, password=password)
    assert response.status_code == 201, response.text
    return response.json()


def create_room(client: httpx.Client, token: str, *, title: str = "Villa K — round 1", client_name: str = "Client") -> dict:
    response = client.post(
        "/rooms",
        headers=auth_headers(token),
        json={"title": title, "clientName": client_name},
    )
    assert response.status_code == 201, response.text
    return response.json()


def get_room(client: httpx.Client, token: str, room_id: str) -> httpx.Response:
    return client.get(f"/rooms/{room_id}", headers=auth_headers(token))


def get_guest_room(client: httpx.Client, guest_token: str) -> httpx.Response:
    return client.get(f"/guest/{guest_token}")


def upload_image(
    client: httpx.Client,
    token: str,
    room_id: str,
    *,
    title: str = "Render",
    filename: str = "render.jpg",
    content: bytes = b"fake-jpeg-bytes",
    content_type: str = "image/jpeg",
) -> httpx.Response:
    return client.post(
        f"/rooms/{room_id}/images",
        headers=auth_headers(token),
        data={"title": title},
        files={"file": (filename, content, content_type)},
    )


def create_guest_pin(
    client: httpx.Client,
    guest_token: str,
    image_id: str,
    *,
    x: float = 50,
    y: float = 50,
    type: str = "fix",
    text: str = "Change the sofa fabric to linen",
    author_name: str = "Client",
) -> httpx.Response:
    return client.post(
        f"/guest/{guest_token}/pins",
        json={
            "imageId": image_id,
            "x": x,
            "y": y,
            "type": type,
            "text": text,
            "authorName": author_name,
        },
    )


def add_guest_comment(client: httpx.Client, guest_token: str, pin_id: str, *, text: str = "Reply", author_name: str = "Client") -> httpx.Response:
    return client.post(
        f"/guest/{guest_token}/pins/{pin_id}/comments",
        json={"text": text, "authorName": author_name},
    )


def add_studio_comment(client: httpx.Client, token: str, pin_id: str, *, text: str = "Reply") -> httpx.Response:
    return client.post(
        f"/pins/{pin_id}/comments",
        headers=auth_headers(token),
        json={"text": text},
    )


def set_pin_status(client: httpx.Client, token: str, pin_id: str, *, status: str) -> httpx.Response:
    return client.patch(
        f"/pins/{pin_id}",
        headers=auth_headers(token),
        json={"status": status},
    )


def guest_approve_round(client: httpx.Client, guest_token: str, *, author_name: str = "Client") -> httpx.Response:
    return client.post(
        f"/guest/{guest_token}/approve",
        json={"authorName": author_name},
    )


def close_room(client: httpx.Client, token: str, room_id: str) -> httpx.Response:
    return client.post(f"/rooms/{room_id}/close", headers=auth_headers(token))
