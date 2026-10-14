"""Pinpoint MCP server: five read-only tools over stdio.

stdout carries nothing but MCP protocol messages (the stdio transport owns it);
anything the server wants to say goes to stderr via ``logging``.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Annotated, Any
from urllib.parse import quote

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from pinpoint_mcp.client import PinpointClient, PinpointError

INSTRUCTIONS = (
    "Read-only access to a running Pinpoint instance (client feedback on renders: "
    "rooms, images, pins). Every tool only reads: no tool creates, resolves, replies "
    "to, approves, closes or deletes anything. Start with list_rooms to find room ids, "
    "then use room_summary for pin counts, open_pins for the open-pin text, or "
    "approve_status for the approval state."
)

RoomId = Annotated[str, Field(description="A room id from `list_rooms`.")]

READ_ONLY = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)

# What a pin counts as. `like` pins carry no status, so they are a single number.
_STATUSED_TYPES = ("fix", "question")
_STATUSES = ("open", "resolved")

_ROOM_LIST_FIELDS = (
    "id",
    "title",
    "clientName",
    "status",
    "createdAt",
    "approvedAt",
    "approvedBy",
    "openPinCount",
)

log = logging.getLogger("pinpoint_mcp")


def _seg(room_id: str) -> str:
    """One URL path segment: a room id can never address another route."""
    return quote(room_id, safe="")


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False)


def _empty_counts() -> dict[str, Any]:
    return {t: {s: 0 for s in _STATUSES} for t in _STATUSED_TYPES} | {"like": 0}


def _count_pin(counts: dict[str, Any], pin: dict[str, Any]) -> None:
    pin_type = pin.get("type")
    if pin_type == "like":
        counts["like"] += 1
    elif pin_type in _STATUSED_TYPES and pin.get("status") in _STATUSES:
        counts[pin_type][pin["status"]] += 1


def summarize_room(detail: dict[str, Any]) -> dict[str, Any]:
    """Pin counts per image and for the whole room from a `RoomDetail` body.

    Superseded images are included and flagged, not hidden: the backend's
    `openPinCount` and the export count them too.
    """
    room = detail["room"]
    pins = detail.get("pins") or []
    totals = _empty_counts()
    images = []
    for image in detail.get("images") or []:
        counts = _empty_counts()
        for pin in pins:
            if pin.get("imageId") == image["id"]:
                _count_pin(counts, pin)
        images.append(
            {
                "id": image["id"],
                "title": image.get("title"),
                "superseded": bool(image.get("superseded")),
                "pins": counts,
            }
        )
    for pin in pins:
        _count_pin(totals, pin)
    return {
        "id": room["id"],
        "title": room.get("title"),
        "clientName": room.get("clientName"),
        "status": room.get("status"),
        "images": images,
        "totals": totals,
    }


async def _guard(call: Any) -> str:
    """Run a tool body, turning every failure into a readable ToolError."""
    try:
        return await call()
    except PinpointError as exc:
        raise ToolError(str(exc)) from None
    except (KeyError, TypeError, AttributeError):
        # A 2xx body that does not look like the documented schema.
        raise ToolError("Pinpoint returned a response in an unexpected shape.") from None


def build_server(client: PinpointClient) -> FastMCP:
    mcp = FastMCP("pinpoint", instructions=INSTRUCTIONS)

    @mcp.tool(annotations=READ_ONLY, structured_output=False)
    async def health() -> str:
        """Check that Pinpoint is reachable; returns its status and deployed commit (no login needed)."""

        async def run() -> str:
            body = await client.get_json("/health", auth=False)
            return _json({"status": body["status"], "commit": body.get("commit")})

        return await _guard(run)

    @mcp.tool(annotations=READ_ONLY, structured_output=False)
    async def list_rooms() -> str:
        """List the studio's rooms with status, approval info and the number of open pins in each."""

        async def run() -> str:
            rooms = await client.get_json("/rooms")
            return _json([{k: room.get(k) for k in _ROOM_LIST_FIELDS} for room in rooms])

        return await _guard(run)

    @mcp.tool(annotations=READ_ONLY, structured_output=False)
    async def room_summary(room_id: RoomId) -> str:
        """Summarise one room: its images and pin counts by type and status, per image and in total."""

        async def run() -> str:
            return _json(summarize_room(await client.get_json(f"/rooms/{_seg(room_id)}")))

        return await _guard(run)

    @mcp.tool(annotations=READ_ONLY, structured_output=False)
    async def open_pins(room_id: RoomId) -> str:
        """Return the room's open fix and question pins as the plain-text export, grouped by image."""

        async def run() -> str:
            return await client.get_text(f"/rooms/{_seg(room_id)}/export")

        return await _guard(run)

    @mcp.tool(annotations=READ_ONLY, structured_output=False)
    async def approve_status(room_id: RoomId) -> str:
        """Report whether the client approved the room, when and by whom.

        `approved` goes back to `open` when a client adds a new fix or question pin
        after approval; `closed` is a separate state set by the studio.
        """

        async def run() -> str:
            room = (await client.get_json(f"/rooms/{_seg(room_id)}"))["room"]
            return _json(
                {
                    "status": room["status"],
                    "approvedAt": room.get("approvedAt"),
                    "approvedBy": room.get("approvedBy"),
                }
            )

        return await _guard(run)

    return mcp


def main() -> None:
    # stderr only: stdout belongs to the MCP protocol.
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    client = PinpointClient.from_env()
    build_server(client).run(transport="stdio")


if __name__ == "__main__":
    main()
