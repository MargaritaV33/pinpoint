"""Approve: a guest approving the round, and a new non-`like` pin
afterward reopening the room."""

from __future__ import annotations

import httpx

from conftest import guest_approve_round, create_guest_pin, create_room, create_studio, get_room, upload_image


def test_guest_approves_room_then_new_pin_reopens_it(client: httpx.Client) -> None:
    session = create_studio(client)
    token = session["token"]
    room = create_room(client, token)
    guest_token = room["guestToken"]
    image = upload_image(client, token, room["id"]).json()

    approve_response = guest_approve_round(client, guest_token)
    assert approve_response.status_code == 200, approve_response.text
    assert approve_response.json()["status"] == "approved"

    new_pin_response = create_guest_pin(client, guest_token, image["id"], type="question")
    assert new_pin_response.status_code == 201, new_pin_response.text

    detail = get_room(client, token, room["id"]).json()
    assert detail["room"]["status"] == "open"
