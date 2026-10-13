"""Persistence across `docker compose restart app`.

Run separately from, and after, the independent scenario suite (see the
root Makefile's `integration` target: two pytest invocations, this file
only in the second one) so a failure in the independent scenarios stops
before anything gets restarted.

Only `app` is restarted — never `postgres` — matching issue #8's QA proof
that this is what makes the check meaningful: a restarted `app` against a
*stopped* in-memory/SQLite store would lose everything; against the real
Postgres container it should not.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import httpx

from conftest import create_room, create_studio, get_guest_room, upload_image

REPO_ROOT = Path(__file__).resolve().parents[2]
HEALTH_POLL_TIMEOUT_SECONDS = 30.0
HEALTH_POLL_INTERVAL_SECONDS = 1.0


def _wait_for_health(base_url: str) -> None:
    deadline = time.monotonic() + HEALTH_POLL_TIMEOUT_SECONDS
    last_error: Exception | None = None
    with httpx.Client(base_url=base_url, timeout=5.0) as health_client:
        while time.monotonic() < deadline:
            try:
                response = health_client.get("/health")
                if response.status_code == 200:
                    return
            except httpx.HTTPError as exc:
                last_error = exc
            time.sleep(HEALTH_POLL_INTERVAL_SECONDS)
    raise AssertionError(
        f"/health did not return 200 within {HEALTH_POLL_TIMEOUT_SECONDS}s after "
        f"`docker compose restart app` (last error: {last_error})"
    )


def test_room_image_and_pin_survive_an_app_restart(client: httpx.Client, base_url: str) -> None:
    session = create_studio(client)
    token = session["token"]
    room = create_room(client, token, title="Persistence check")
    guest_token = room["guestToken"]
    image = upload_image(client, token, room["id"], title="Persistence render").json()

    pin_response = client.post(
        f"/guest/{guest_token}/pins",
        json={
            "imageId": image["id"],
            "x": 50,
            "y": 50,
            "type": "fix",
            "text": "Still here after restart?",
            "authorName": "Client",
        },
    )
    assert pin_response.status_code == 201, pin_response.text
    pin = pin_response.json()

    subprocess.run(["docker", "compose", "restart", "app"], cwd=REPO_ROOT, check=True)

    _wait_for_health(base_url)

    detail_response = get_guest_room(client, guest_token)
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()

    assert detail["room"]["title"] == "Persistence check"
    assert any(i["id"] == image["id"] for i in detail["images"])
    assert any(p["id"] == pin["id"] for p in detail["pins"])
