from __future__ import annotations

from fastapi.testclient import TestClient

TINY_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100 + b"\xff\xd9"


def _second_studio_room(client: TestClient) -> tuple[dict[str, str], str]:
    signup = client.post("/auth/signup", json={"email": "other@studio.example", "password": "s3cret"})
    headers = {"Authorization": f"Bearer {signup.json()['token']}"}
    created = client.post("/rooms", json={"title": "Other's Room", "clientName": "X"}, headers=headers)
    return headers, created.json()["id"]


# -- uploadImage -----------------------------------------------------------------

def test_upload_image_happy_path(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/rooms/r_lakeside/images",
        data={"title": "New render"},
        files={"file": ("render.jpg", TINY_JPEG, "image/jpeg")},
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "New render"
    assert body["superseded"] is False
    assert body["url"]


def test_upload_image_blank_title_is_400(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/rooms/r_lakeside/images",
        data={"title": "   "},
        files={"file": ("render.jpg", TINY_JPEG, "image/jpeg")},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_upload_image_disallowed_type_is_415(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/rooms/r_lakeside/images",
        data={"title": "Bad type"},
        files={"file": ("render.gif", TINY_JPEG, "image/gif")},
        headers=auth_headers,
    )
    assert response.status_code == 415


def test_upload_image_too_large_is_413(client: TestClient, auth_headers: dict[str, str]) -> None:
    oversize = b"\x00" * (15 * 1024 * 1024 + 1)
    response = client.post(
        "/rooms/r_lakeside/images",
        data={"title": "Too big"},
        files={"file": ("render.jpg", oversize, "image/jpeg")},
        headers=auth_headers,
    )
    assert response.status_code == 413


def test_upload_image_closed_room_is_403(client: TestClient, auth_headers: dict[str, str]) -> None:
    client.post("/rooms/r_lakeside/close", headers=auth_headers)
    response = client.post(
        "/rooms/r_lakeside/images",
        data={"title": "New render"},
        files={"file": ("render.jpg", TINY_JPEG, "image/jpeg")},
        headers=auth_headers,
    )
    assert response.status_code == 403


def test_upload_image_cross_owner_is_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/rooms/r_atrium/images".replace("r_atrium", "r_atrium"),
        data={"title": "New render"},
        files={"file": ("render.jpg", TINY_JPEG, "image/jpeg")},
        headers=_second_studio_room(client)[0],
    )
    assert response.status_code == 404


# -- setImageSuperseded -----------------------------------------------------------

def test_set_image_superseded_toggles(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.patch("/images/i_facade", json={"superseded": True}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["superseded"] is True

    response = client.patch("/images/i_facade", json={"superseded": False}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["superseded"] is False


def test_set_image_superseded_closed_room_is_403(client: TestClient, auth_headers: dict[str, str]) -> None:
    client.post("/rooms/r_lakeside/close", headers=auth_headers)
    response = client.patch("/images/i_facade", json={"superseded": True}, headers=auth_headers)
    assert response.status_code == 403


def test_set_image_superseded_cross_owner_is_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    other_headers, _ = _second_studio_room(client)
    response = client.patch("/images/i_facade", json={"superseded": True}, headers=other_headers)
    assert response.status_code == 404


# -- getRoomImageFile --------------------------------------------------------------

def test_get_room_image_file_happy_path(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/rooms/r_lakeside/images/i_facade/file", headers=auth_headers)

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["etag"]
    assert response.headers["cache-control"]
    assert len(response.content) > 0


def test_get_room_image_file_unknown_image_is_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/rooms/r_lakeside/images/does-not-exist/file", headers=auth_headers)
    assert response.status_code == 404


# -- seed images are the real demo photos, not flat-color placeholders ------------
# The old placeholders were a few KB; the real renders copied from
# `frontend/src/assets/render-*.jpg` are well over 100 KB. A byte-length floor
# well above the old placeholder size (but safely below any real photo)
# proves the actual photo is being served, not just a same-named file.
_OLD_PLACEHOLDER_MAX_BYTES = 10_000


def test_guest_seed_image_is_real_photo_not_placeholder(client: TestClient) -> None:
    response = client.get("/guest/lakeside-demo/images/i_facade/file")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert len(response.content) > _OLD_PLACEHOLDER_MAX_BYTES


def test_studio_seed_images_are_real_photos_not_placeholders(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    for room_id, image_id in [("r_lakeside", "i_facade"), ("r_lakeside", "i_living"), ("r_atrium", "i_atrium")]:
        response = client.get(f"/rooms/{room_id}/images/{image_id}/file", headers=auth_headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"
        assert len(response.content) > _OLD_PLACEHOLDER_MAX_BYTES


def test_get_room_image_file_cross_room_is_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    # i_atrium belongs to r_atrium, not r_lakeside.
    response = client.get("/rooms/r_lakeside/images/i_atrium/file", headers=auth_headers)
    assert response.status_code == 404
