"""Room lifecycle: create, list with openPinCount, close, and closed-room
rejections (upload / pin status / comment all 403)."""

from __future__ import annotations

import httpx

from conftest import (
    add_studio_comment,
    close_room,
    create_guest_pin,
    create_room,
    create_studio,
    set_pin_status,
    upload_image,
)


def test_create_room_and_list_shows_open_pin_count(client: httpx.Client) -> None:
    session = create_studio(client)
    token = session["token"]
    room = create_room(client, token)
    assert room["status"] == "open"
    guest_token = room["guestToken"]

    image_response = upload_image(client, token, room["id"])
    assert image_response.status_code == 201, image_response.text
    image = image_response.json()

    fix_pin_response = create_guest_pin(client, guest_token, image["id"], type="fix")
    assert fix_pin_response.status_code == 201, fix_pin_response.text

    like_pin_response = create_guest_pin(client, guest_token, image["id"], type="like")
    assert like_pin_response.status_code == 201, like_pin_response.text

    list_response = client.get("/rooms", headers={"Authorization": f"Bearer {token}"})
    assert list_response.status_code == 200, list_response.text
    rooms = list_response.json()
    listed = next(r for r in rooms if r["id"] == room["id"])
    # Only the `fix` pin is `open` and counted; the `like` pin has no status.
    assert listed["openPinCount"] == 1


def test_close_room_then_upload_pin_status_and_comment_all_403(client: httpx.Client) -> None:
    session = create_studio(client)
    token = session["token"]
    room = create_room(client, token)
    guest_token = room["guestToken"]

    image_response = upload_image(client, token, room["id"])
    assert image_response.status_code == 201, image_response.text
    image = image_response.json()

    pin_response = create_guest_pin(client, guest_token, image["id"], type="fix")
    assert pin_response.status_code == 201, pin_response.text
    pin = pin_response.json()

    close_response = close_room(client, token, room["id"])
    assert close_response.status_code == 200, close_response.text
    assert close_response.json()["status"] == "closed"

    upload_after_close = upload_image(client, token, room["id"])
    assert upload_after_close.status_code == 403, upload_after_close.text

    pin_status_after_close = set_pin_status(client, token, pin["id"], status="resolved")
    assert pin_status_after_close.status_code == 403, pin_status_after_close.text

    comment_after_close = add_studio_comment(client, token, pin["id"])
    assert comment_after_close.status_code == 403, comment_after_close.text
