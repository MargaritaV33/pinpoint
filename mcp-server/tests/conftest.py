"""Shared fixtures: payloads shaped like openapi.yaml's schemas, a respx router
that rejects every unmocked request, and a helper that calls a tool through the
real MCP protocol (in-memory transport) so `isError` is what a client sees."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
import respx
from mcp.shared.memory import create_connected_server_and_client_session

from pinpoint_mcp.client import PinpointClient
from pinpoint_mcp.server import build_server

BASE = "http://pinpoint.test"
TOKEN = "tok-SECRET-123"
EMAIL = "demo@pinpoint.studio"
PASSWORD = "pw-SECRET-456"
LAKESIDE_GUEST_TOKEN = "lakeside-GUEST-789"
ATRIUM_GUEST_TOKEN = "atrium-GUEST-789"


def room(id_: str, title: str, client: str, status: str, guest: str, approved_at=None, approved_by=None) -> dict:
    return {
        "id": id_,
        "title": title,
        "clientName": client,
        "createdAt": "2026-10-05T09:12:00Z",
        "status": status,
        "guestToken": guest,
        "approvedAt": approved_at,
        "approvedBy": approved_by,
    }


LAKESIDE = room("r_lakeside", "Lakeside Villa — Round 2", "Marta Lind", "open", LAKESIDE_GUEST_TOKEN)
ATRIUM = room(
    "r_atrium", "Harbour Office Atrium", "Nordvik Properties", "approved", ATRIUM_GUEST_TOKEN,
    "2026-09-28T10:00:00Z", "Jonas Berg",
)


def image(id_: str, room_id: str, title: str, superseded: bool = False) -> dict:
    return {
        "id": id_,
        "roomId": room_id,
        "title": title,
        "url": f"/rooms/{room_id}/images/{id_}/file",
        "superseded": superseded,
        "createdAt": "2026-10-05T09:15:00Z",
    }


def pin(id_: str, image_id: str, number: int, type_: str, status: str | None) -> dict:
    return {
        "id": id_,
        "imageId": image_id,
        "number": number,
        "x": 10.0,
        "y": 20.0,
        "type": type_,
        "status": status,
        "createdAt": "2026-10-06T08:01:00Z",
        "comments": [],
    }


LAKESIDE_DETAIL = {
    "room": LAKESIDE,
    "images": [
        image("i_facade", "r_lakeside", "Lake facade, golden hour"),
        image("i_living", "r_lakeside", "Living room"),
    ],
    "pins": [
        pin("p1", "i_facade", 1, "fix", "open"),
        pin("p2", "i_facade", 2, "question", "open"),
        pin("p3", "i_facade", 3, "like", None),
        pin("p4", "i_living", 1, "fix", "resolved"),
        pin("p5", "i_living", 2, "like", None),
    ],
}

ATRIUM_DETAIL = {
    "room": ATRIUM,
    "images": [image("i_atrium", "r_atrium", "Atrium, ground level")],
    "pins": [pin("p6", "i_atrium", 1, "like", None), pin("p7", "i_atrium", 2, "fix", "resolved")],
}

LAKESIDE_EXPORT = (
    "Pinpoint — open pins\nRoom: Lakeside Villa — Round 2\nClient: Marta Lind\n"
    "Exported: 2026-10-14 10:00\n\n== Lake facade, golden hour ==\n"
    "#1 [fix] Could the cladding be a shade darker? — Marta Lind (1 reply)\n"
    "#2 [question] Is the lake level right? — Marta Lind\n"
)
ATRIUM_EXPORT = (
    "Pinpoint — open pins\nRoom: Harbour Office Atrium\nClient: Nordvik Properties\n"
    "Exported: 2026-10-14 10:00\n\nNo open pins.\n"
)

NOT_FOUND = {"detail": "No such room, or it belongs to a different studio user."}


def session(token: str = TOKEN) -> dict:
    return {"token": token, "user": {"id": "u_demo", "email": EMAIL, "name": "Studio Halden"}}


def summary(room_dict: dict, open_pins: int) -> dict:
    return {**room_dict, "openPinCount": open_pins}


@pytest.fixture
def api():
    """A respx router; any request without a route fails the test."""
    with respx.MockRouter(base_url=BASE, assert_all_called=False) as router:
        yield router


def mock_demo_rooms(api: respx.MockRouter) -> None:
    """Routes for the seed data (every route is a GET)."""
    text = {"content-type": "text/plain; charset=utf-8"}
    api.get("/health").respond(json={"status": "ok", "commit": None})
    api.get("/rooms").respond(json=[summary(LAKESIDE, 2), summary(ATRIUM, 0)])
    api.get("/rooms/r_lakeside").respond(json=LAKESIDE_DETAIL)
    api.get("/rooms/r_atrium").respond(json=ATRIUM_DETAIL)
    api.get("/rooms/r_lakeside/export").respond(text=LAKESIDE_EXPORT, headers=text)
    api.get("/rooms/r_atrium/export").respond(text=ATRIUM_EXPORT, headers=text)
    api.get("/rooms/nope").respond(404, json=NOT_FOUND)
    api.get("/rooms/nope/export").respond(404, json=NOT_FOUND)


def make_client(**kwargs: Any) -> PinpointClient:
    kwargs.setdefault("base_url", BASE)
    return PinpointClient(**kwargs)


async def _call(client: PinpointClient, name: str, arguments: dict[str, Any]) -> tuple[bool, str]:
    server = build_server(client)
    async with create_connected_server_and_client_session(server._mcp_server) as mcp_client:
        result = await mcp_client.call_tool(name, arguments)
    return result.isError, "\n".join(c.text for c in result.content if c.type == "text")


def call(client: PinpointClient, name: str, **arguments: Any) -> tuple[bool, str]:
    """Call a tool through the MCP protocol; returns (isError, text)."""
    return asyncio.run(_call(client, name, arguments))


def requests_made(api: respx.MockRouter) -> list[tuple[str, str]]:
    return [(c.request.method, c.request.url.path) for c in api.calls]
