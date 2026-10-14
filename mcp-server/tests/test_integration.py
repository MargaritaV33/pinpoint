"""Integration test against a real, running Pinpoint (`make up`).

Skipped, loudly, unless PINPOINT_BASE_URL is set, so the unit run and CI's
`mcp` job report it as SKIPPED rather than passing it silently. Uses
PINPOINT_EMAIL / PINPOINT_PASSWORD if set, else the seeded demo account
(public in the repo README). PINPOINT_TOKEN is deliberately ignored here: this
test exercises the login path against the real backend.

Run it:  PINPOINT_BASE_URL=http://localhost:8100 uv run pytest tests/test_integration.py -rs
"""

import asyncio
import json
import os

import pytest

from pinpoint_mcp.client import PinpointClient
from pinpoint_mcp.server import build_server

pytestmark = pytest.mark.skipif(
    not os.environ.get("PINPOINT_BASE_URL", "").strip(),
    reason="PINPOINT_BASE_URL is not set (integration test needs a running Pinpoint, see `make up`)",
)


@pytest.fixture(scope="module")
def client() -> PinpointClient:
    return PinpointClient(
        base_url=os.environ["PINPOINT_BASE_URL"],
        email=os.environ.get("PINPOINT_EMAIL", "").strip() or "demo@pinpoint.studio",
        password=os.environ.get("PINPOINT_PASSWORD", "") or "pinpoint",
    )


def tool(client: PinpointClient, name: str, **arguments) -> str:
    async def run() -> str:
        result = await build_server(client).call_tool(name, arguments)
        return result[0].text if isinstance(result, (list, tuple)) else str(result)

    return asyncio.run(run())


def test_health_is_ok(client):
    assert json.loads(tool(client, "health"))["status"] == "ok"


def test_list_rooms_contains_both_demo_rooms(client):
    rooms = {r["id"]: r for r in json.loads(tool(client, "list_rooms"))}
    assert {"r_lakeside", "r_atrium"} <= set(rooms)
    assert rooms["r_lakeside"]["title"] == "Lakeside Villa — Round 2"
    assert rooms["r_lakeside"]["status"] == "open" and rooms["r_lakeside"]["openPinCount"] == 2
    assert rooms["r_atrium"]["title"] == "Harbour Office Atrium"
    assert rooms["r_atrium"]["status"] == "approved" and rooms["r_atrium"]["openPinCount"] == 0
    assert all("guestToken" not in r for r in rooms.values())


def test_room_summary_lakeside_reports_one_open_fix(client):
    totals = json.loads(tool(client, "room_summary", room_id="r_lakeside"))["totals"]
    assert totals["fix"]["open"] == 1


def test_open_pins_atrium_has_none(client):
    assert "No open pins." in tool(client, "open_pins", room_id="r_atrium")


def test_approve_status_atrium_is_approved(client):
    out = json.loads(tool(client, "approve_status", room_id="r_atrium"))
    assert out["status"] == "approved" and out["approvedBy"] == "Jonas Berg"


def test_only_get_requests_and_the_login_post_were_issued(client):
    # Runs last (file order): everything above went through this same client.
    assert client.request_log, "no requests recorded"
    allowed_get = {"/health", "/rooms", "/rooms/r_lakeside", "/rooms/r_atrium/export", "/rooms/r_atrium"}
    for method, path in client.request_log:
        assert (method, path) == ("POST", "/auth/login") or (method == "GET" and path in allowed_get), (
            method, path,
        )
