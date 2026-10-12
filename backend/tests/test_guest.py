from __future__ import annotations

from fastapi.testclient import TestClient

TINY_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100 + b"\xff\xd9"


# -- getGuestRoom ----------------------------------------------------------------

def test_get_guest_room_happy_path(client: TestClient) -> None:
    response = client.get("/guest/lakeside-demo")

    assert response.status_code == 200
    body = response.json()
    assert body["room"]["id"] == "r_lakeside"
    assert len(body["images"]) == 2
    assert len(body["pins"]) == 5


def test_get_guest_room_unknown_token_is_404(client: TestClient) -> None:
    response = client.get("/guest/not-a-real-token")
    assert response.status_code == 404


# -- createGuestPin ----------------------------------------------------------------

def test_create_guest_pin_happy_path(client: TestClient) -> None:
    response = client.post(
        "/guest/lakeside-demo/pins",
        json={"imageId": "i_facade", "x": 10.0, "y": 20.0, "type": "fix", "text": "Fix this", "authorName": "Marta"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "open"
    assert len(body["comments"]) == 1


def test_sequential_pin_numbering_per_image(client: TestClient, auth_headers: dict[str, str]) -> None:
    # i_facade already has pins 1-3 in the seed; a new pin on it is #4.
    response = client.post(
        "/guest/lakeside-demo/pins",
        json={"imageId": "i_facade", "x": 1.0, "y": 1.0, "type": "fix", "text": "Fourth", "authorName": "Marta"},
    )
    assert response.status_code == 201
    assert response.json()["number"] == 4

    # A different, empty image's first pin is #1, independent of i_facade's numbering.
    upload = client.post(
        "/rooms/r_lakeside/images",
        data={"title": "Fresh render"},
        files={"file": ("render.jpg", TINY_JPEG, "image/jpeg")},
        headers=auth_headers,
    )
    new_image_id = upload.json()["id"]

    first = client.post(
        "/guest/lakeside-demo/pins",
        json={"imageId": new_image_id, "x": 1.0, "y": 1.0, "type": "fix", "text": "First here", "authorName": "Marta"},
    )
    assert first.json()["number"] == 1

    second = client.post(
        "/guest/lakeside-demo/pins",
        json={"imageId": new_image_id, "x": 2.0, "y": 2.0, "type": "question", "text": "Second here", "authorName": "Marta"},
    )
    assert second.json()["number"] == 2


def test_create_guest_pin_blank_author_name_is_400(client: TestClient) -> None:
    response = client.post(
        "/guest/lakeside-demo/pins",
        json={"imageId": "i_facade", "x": 10.0, "y": 20.0, "type": "fix", "text": "Fix this", "authorName": "  "},
    )
    assert response.status_code == 400


def test_create_guest_pin_out_of_range_position_is_400(client: TestClient) -> None:
    response = client.post(
        "/guest/lakeside-demo/pins",
        json={"imageId": "i_facade", "x": 150.0, "y": 20.0, "type": "fix", "text": "Fix this", "authorName": "Marta"},
    )
    assert response.status_code == 400


def test_create_guest_pin_closed_room_is_403(client: TestClient, auth_headers: dict[str, str]) -> None:
    client.post("/rooms/r_lakeside/close", headers=auth_headers)
    response = client.post(
        "/guest/lakeside-demo/pins",
        json={"imageId": "i_facade", "x": 10.0, "y": 20.0, "type": "fix", "text": "Fix this", "authorName": "Marta"},
    )
    assert response.status_code == 403


def test_create_guest_pin_unknown_image_is_404(client: TestClient) -> None:
    response = client.post(
        "/guest/lakeside-demo/pins",
        json={"imageId": "does-not-exist", "x": 10.0, "y": 20.0, "type": "fix", "text": "Fix this", "authorName": "Marta"},
    )
    assert response.status_code == 404


def test_create_guest_pin_on_superseded_image_is_409(client: TestClient, auth_headers: dict[str, str]) -> None:
    client.patch("/images/i_facade", json={"superseded": True}, headers=auth_headers)
    response = client.post(
        "/guest/lakeside-demo/pins",
        json={"imageId": "i_facade", "x": 10.0, "y": 20.0, "type": "fix", "text": "Fix this", "authorName": "Marta"},
    )
    assert response.status_code == 409


def test_new_fix_pin_reopens_an_approved_room(client: TestClient) -> None:
    before = client.get("/guest/atrium-demo").json()
    assert before["room"]["status"] == "approved"

    response = client.post(
        "/guest/atrium-demo/pins",
        json={"imageId": "i_atrium", "x": 5.0, "y": 5.0, "type": "fix", "text": "One more thing", "authorName": "Jonas"},
    )
    assert response.status_code == 201

    after = client.get("/guest/atrium-demo").json()
    assert after["room"]["status"] == "open"


def test_like_pin_leaves_an_approved_room_approved(client: TestClient) -> None:
    response = client.post(
        "/guest/atrium-demo/pins",
        json={"imageId": "i_atrium", "x": 5.0, "y": 5.0, "type": "like", "text": "Love it", "authorName": "Jonas"},
    )
    assert response.status_code == 201

    after = client.get("/guest/atrium-demo").json()
    assert after["room"]["status"] == "approved"


# -- addGuestComment -----------------------------------------------------------------

def test_add_guest_comment_happy_path(client: TestClient) -> None:
    response = client.post("/guest/lakeside-demo/pins/p1/comments", json={"text": "Any update?", "authorName": "Marta"})

    assert response.status_code == 201
    assert response.json()["authorRole"] == "client"


def test_guest_reply_reopens_a_resolved_pin(client: TestClient) -> None:
    # p4 is `resolved` in the seed.
    response = client.post("/guest/lakeside-demo/pins/p4/comments", json={"text": "Still an issue", "authorName": "Marta"})
    assert response.status_code == 201

    room = client.get("/guest/lakeside-demo").json()
    p4 = next(p for p in room["pins"] if p["id"] == "p4")
    assert p4["status"] == "open"


def test_guest_reply_to_open_pin_leaves_it_open(client: TestClient) -> None:
    # p1 is already `open` in the seed.
    response = client.post("/guest/lakeside-demo/pins/p1/comments", json={"text": "Following up", "authorName": "Marta"})
    assert response.status_code == 201

    room = client.get("/guest/lakeside-demo").json()
    p1 = next(p for p in room["pins"] if p["id"] == "p1")
    assert p1["status"] == "open"


def test_guest_reply_to_like_pin_leaves_status_null(client: TestClient) -> None:
    # p3 is a `like` pin.
    response = client.post("/guest/lakeside-demo/pins/p3/comments", json={"text": "Still love it", "authorName": "Marta"})
    assert response.status_code == 201

    room = client.get("/guest/lakeside-demo").json()
    p3 = next(p for p in room["pins"] if p["id"] == "p3")
    assert p3["status"] is None


def test_add_guest_comment_blank_text_is_400(client: TestClient) -> None:
    response = client.post("/guest/lakeside-demo/pins/p1/comments", json={"text": "   ", "authorName": "Marta"})
    assert response.status_code == 400


def test_add_guest_comment_closed_room_is_403(client: TestClient, auth_headers: dict[str, str]) -> None:
    client.post("/rooms/r_lakeside/close", headers=auth_headers)
    response = client.post("/guest/lakeside-demo/pins/p1/comments", json={"text": "Hi", "authorName": "Marta"})
    assert response.status_code == 403


def test_add_guest_comment_cross_room_token_is_404(client: TestClient) -> None:
    # p7 belongs to r_atrium, not r_lakeside.
    response = client.post("/guest/lakeside-demo/pins/p7/comments", json={"text": "Hi", "authorName": "Marta"})
    assert response.status_code == 404


# -- approveRound -----------------------------------------------------------------------

def test_approve_round_happy_path(client: TestClient) -> None:
    response = client.post("/guest/lakeside-demo/approve", json={"authorName": "Marta Lind"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert body["approvedBy"] == "Marta Lind"


def test_approve_round_unknown_token_is_404(client: TestClient) -> None:
    response = client.post("/guest/not-a-real-token/approve", json={"authorName": "Marta Lind"})
    assert response.status_code == 404


def test_approve_round_closed_room_is_403(client: TestClient, auth_headers: dict[str, str]) -> None:
    client.post("/rooms/r_lakeside/close", headers=auth_headers)
    response = client.post("/guest/lakeside-demo/approve", json={"authorName": "Marta Lind"})
    assert response.status_code == 403


# -- getGuestImageFile --------------------------------------------------------------------

def test_get_guest_image_file_happy_path(client: TestClient) -> None:
    response = client.get("/guest/lakeside-demo/images/i_facade/file")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["etag"]
    assert response.headers["cache-control"]
    assert len(response.content) > 0


def test_get_guest_image_file_cross_room_token_is_404(client: TestClient) -> None:
    # i_atrium belongs to r_atrium, not r_lakeside's guest token.
    response = client.get("/guest/lakeside-demo/images/i_atrium/file")
    assert response.status_code == 404


def test_get_guest_image_file_unknown_token_is_404(client: TestClient) -> None:
    response = client.get("/guest/not-a-real-token/images/i_facade/file")
    assert response.status_code == 404
