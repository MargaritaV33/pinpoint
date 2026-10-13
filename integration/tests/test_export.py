"""Export: `text/plain`, grouped by image, excluding resolved and `like`
pins."""

from __future__ import annotations

import httpx

from conftest import auth_headers, create_guest_pin, create_room, create_studio, set_pin_status, upload_image

OPEN_FIX_TEXT = "Change the sofa fabric to linen"
RESOLVED_FIX_TEXT = "Move the lamp to the left wall"
LIKE_TEXT = "Love this angle"


def test_export_excludes_resolved_and_like_pins(client: httpx.Client) -> None:
    session = create_studio(client)
    token = session["token"]
    room = create_room(client, token)
    guest_token = room["guestToken"]
    image = upload_image(client, token, room["id"]).json()

    open_fix_pin = create_guest_pin(client, guest_token, image["id"], type="fix", text=OPEN_FIX_TEXT).json()

    resolved_fix_pin = create_guest_pin(client, guest_token, image["id"], type="fix", text=RESOLVED_FIX_TEXT).json()
    resolve_response = set_pin_status(client, token, resolved_fix_pin["id"], status="resolved")
    assert resolve_response.status_code == 200, resolve_response.text

    like_pin_response = create_guest_pin(client, guest_token, image["id"], type="like", text=LIKE_TEXT)
    assert like_pin_response.status_code == 201, like_pin_response.text

    export_response = client.get(f"/rooms/{room['id']}/export", headers=auth_headers(token))
    assert export_response.status_code == 200, export_response.text
    assert export_response.headers["content-type"].startswith("text/plain")

    body = export_response.text
    assert f"== {image['title']} ==" in body
    assert OPEN_FIX_TEXT in body
    assert RESOLVED_FIX_TEXT not in body
    assert LIKE_TEXT not in body
