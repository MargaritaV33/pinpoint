"""Upload: happy path, oversize (413), wrong type (415), and byte-serving
with a stable ETag.

No conditional-GET/304 logic exists anywhere in this codebase (confirmed by
reading `backend/app/serializers.py`'s `image_file_response`, which sets
`ETag`/`Cache-Control` but never reads `If-None-Match`). This test only
checks the header is present and stable across two plain GETs — it does not
send `If-None-Match` or assert a `304`.
"""

from __future__ import annotations

import httpx

from conftest import auth_headers, create_room, create_studio, upload_image

FIFTEEN_MB = 15 * 1024 * 1024


def test_upload_happy_path_then_bytes_have_a_stable_etag(client: httpx.Client) -> None:
    session = create_studio(client)
    token = session["token"]
    room = create_room(client, token)

    upload_response = upload_image(client, token, room["id"])
    assert upload_response.status_code == 201, upload_response.text
    image = upload_response.json()

    first_get = client.get(f"/rooms/{room['id']}/images/{image['id']}/file", headers=auth_headers(token))
    assert first_get.status_code == 200, first_get.text
    first_etag = first_get.headers.get("etag")
    assert first_etag

    second_get = client.get(f"/rooms/{room['id']}/images/{image['id']}/file", headers=auth_headers(token))
    assert second_get.status_code == 200, second_get.text
    second_etag = second_get.headers.get("etag")
    assert second_etag == first_etag


def test_upload_oversize_file_returns_413(client: httpx.Client) -> None:
    session = create_studio(client)
    token = session["token"]
    room = create_room(client, token)

    oversize_content = b"\x00" * (FIFTEEN_MB + 1)
    response = upload_image(client, token, room["id"], content=oversize_content)
    assert response.status_code == 413, response.text


def test_upload_disallowed_type_returns_415(client: httpx.Client) -> None:
    session = create_studio(client)
    token = session["token"]
    room = create_room(client, token)

    response = upload_image(
        client,
        token,
        room["id"],
        filename="render.gif",
        content=b"fake-gif-bytes",
        content_type="image/gif",
    )
    assert response.status_code == 415, response.text
