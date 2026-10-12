from __future__ import annotations

from fastapi.testclient import TestClient


def _second_studio_headers(client: TestClient) -> dict[str, str]:
    signup = client.post("/auth/signup", json={"email": "other@studio.example", "password": "s3cret"})
    token = signup.json()["token"]
    return {"Authorization": f"Bearer {token}"}


# -- listRooms -----------------------------------------------------------------

def test_list_rooms_happy_path(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/rooms", headers=auth_headers)

    assert response.status_code == 200
    by_id = {room["id"]: room for room in response.json()}
    assert by_id["r_lakeside"]["openPinCount"] == 2
    assert by_id["r_atrium"]["openPinCount"] == 0


def test_list_rooms_without_token_is_401(client: TestClient) -> None:
    response = client.get("/rooms")
    assert response.status_code == 401


# -- createRoom -----------------------------------------------------------------

def test_create_room_happy_path(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post("/rooms", json={"title": "New Build", "clientName": "A. Client"}, headers=auth_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "New Build"
    assert body["status"] == "open"
    assert body["guestToken"]


def test_create_room_blank_title_is_400(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post("/rooms", json={"title": "  ", "clientName": "A. Client"}, headers=auth_headers)
    assert response.status_code == 400


# -- getRoom ---------------------------------------------------------------------

def test_get_room_happy_path(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/rooms/r_lakeside", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["room"]["id"] == "r_lakeside"
    assert len(body["images"]) == 2
    assert len(body["pins"]) == 5


def test_get_room_unknown_id_is_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/rooms/does-not-exist", headers=auth_headers)
    assert response.status_code == 404


def test_get_room_cross_owner_is_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    other_headers = _second_studio_headers(client)
    created = client.post("/rooms", json={"title": "Other's Room", "clientName": "X"}, headers=other_headers)
    other_room_id = created.json()["id"]

    response = client.get(f"/rooms/{other_room_id}", headers=auth_headers)
    assert response.status_code == 404


# -- closeRoom -------------------------------------------------------------------

def test_close_room_happy_path(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post("/rooms/r_lakeside/close", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "closed"


def test_close_room_cross_owner_is_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    other_headers = _second_studio_headers(client)
    created = client.post("/rooms", json={"title": "Other's Room", "clientName": "X"}, headers=other_headers)
    other_room_id = created.json()["id"]

    response = client.post(f"/rooms/{other_room_id}/close", headers=auth_headers)
    assert response.status_code == 404


# -- exportOpenPins ----------------------------------------------------------------

def test_export_open_pins_happy_path(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/rooms/r_lakeside/export", headers=auth_headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    text = response.text
    # i_facade has two open pins (#1 fix, #2 question); i_living's only
    # non-like pin is resolved, so it must be excluded entirely.
    assert "Lake facade, golden hour" in text
    assert "#1 [fix]" in text
    assert "#2 [question]" in text
    assert "Living room" not in text


def test_export_open_pins_cross_owner_is_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    other_headers = _second_studio_headers(client)
    created = client.post("/rooms", json={"title": "Other's Room", "clientName": "X"}, headers=other_headers)
    other_room_id = created.json()["id"]

    response = client.get(f"/rooms/{other_room_id}/export", headers=auth_headers)
    assert response.status_code == 404
