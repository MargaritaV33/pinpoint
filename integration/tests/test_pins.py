"""Pin thread: like pins have no status, resolving a fix pin, a guest reply
reopening a resolved pin, and a studio reply never reopening one."""

from __future__ import annotations

import httpx

from conftest import (
    add_guest_comment,
    add_studio_comment,
    create_guest_pin,
    create_room,
    create_studio,
    get_guest_room,
    get_room,
    set_pin_status,
    upload_image,
)


def _setup_room_with_image(client: httpx.Client) -> tuple[dict, str, dict]:
    session = create_studio(client)
    token = session["token"]
    room = create_room(client, token)
    image = upload_image(client, token, room["id"]).json()
    return room, token, image


def test_like_pin_has_null_status_and_patch_returns_400(client: httpx.Client) -> None:
    room, token, image = _setup_room_with_image(client)
    guest_token = room["guestToken"]

    like_pin = create_guest_pin(client, guest_token, image["id"], type="like").json()
    assert like_pin["status"] is None

    patch_response = set_pin_status(client, token, like_pin["id"], status="resolved")
    assert patch_response.status_code == 400, patch_response.text


def test_resolve_fix_pin_then_guest_reply_reopens_it(client: httpx.Client) -> None:
    room, token, image = _setup_room_with_image(client)
    guest_token = room["guestToken"]

    fix_pin = create_guest_pin(client, guest_token, image["id"], type="fix").json()

    resolve_response = set_pin_status(client, token, fix_pin["id"], status="resolved")
    assert resolve_response.status_code == 200, resolve_response.text
    assert resolve_response.json()["status"] == "resolved"

    reply_response = add_guest_comment(client, guest_token, fix_pin["id"])
    assert reply_response.status_code == 201, reply_response.text

    detail = get_guest_room(client, guest_token).json()
    reopened_pin = next(p for p in detail["pins"] if p["id"] == fix_pin["id"])
    assert reopened_pin["status"] == "open"


def test_studio_reply_to_resolved_pin_never_reopens_it(client: httpx.Client) -> None:
    room, token, image = _setup_room_with_image(client)
    guest_token = room["guestToken"]

    fix_pin = create_guest_pin(client, guest_token, image["id"], type="fix").json()

    resolve_response = set_pin_status(client, token, fix_pin["id"], status="resolved")
    assert resolve_response.status_code == 200, resolve_response.text

    studio_reply_response = add_studio_comment(client, token, fix_pin["id"])
    assert studio_reply_response.status_code == 201, studio_reply_response.text

    detail = get_room(client, token, room["id"]).json()
    pin = next(p for p in detail["pins"] if p["id"] == fix_pin["id"])
    assert pin["status"] == "resolved"
