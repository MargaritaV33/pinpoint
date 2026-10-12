from __future__ import annotations

from fastapi.testclient import TestClient


def _second_studio_headers(client: TestClient) -> dict[str, str]:
    signup = client.post("/auth/signup", json={"email": "other@studio.example", "password": "s3cret"})
    return {"Authorization": f"Bearer {signup.json()['token']}"}


# -- setPinStatus ----------------------------------------------------------------

def test_set_pin_status_happy_path(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.patch("/pins/p1", json={"status": "resolved"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "resolved"

    response = client.patch("/pins/p1", json={"status": "open"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "open"


def test_set_pin_status_on_like_pin_is_400(client: TestClient, auth_headers: dict[str, str]) -> None:
    # p3 is a `like` pin on i_facade.
    response = client.patch("/pins/p3", json={"status": "resolved"}, headers=auth_headers)
    assert response.status_code == 400


def test_set_pin_status_closed_room_is_403(client: TestClient, auth_headers: dict[str, str]) -> None:
    client.post("/rooms/r_lakeside/close", headers=auth_headers)
    response = client.patch("/pins/p1", json={"status": "resolved"}, headers=auth_headers)
    assert response.status_code == 403


def test_set_pin_status_cross_owner_is_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    other_headers = _second_studio_headers(client)
    response = client.patch("/pins/p1", json={"status": "resolved"}, headers=other_headers)
    assert response.status_code == 404


# -- addStudioComment --------------------------------------------------------------

def test_add_studio_comment_happy_path(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post("/pins/p1/comments", json={"text": "Looking into it."}, headers=auth_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["text"] == "Looking into it."
    assert body["authorRole"] == "studio"


def test_studio_reply_never_reopens_a_resolved_pin(client: TestClient, auth_headers: dict[str, str]) -> None:
    # p4 is already `resolved` in the seed.
    response = client.post("/pins/p4/comments", json={"text": "Just confirming."}, headers=auth_headers)
    assert response.status_code == 201

    pin = client.get("/rooms/r_lakeside", headers=auth_headers).json()["pins"]
    p4 = next(p for p in pin if p["id"] == "p4")
    assert p4["status"] == "resolved"


def test_add_studio_comment_blank_text_is_400(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post("/pins/p1/comments", json={"text": "   "}, headers=auth_headers)
    assert response.status_code == 400


def test_add_studio_comment_closed_room_is_403(client: TestClient, auth_headers: dict[str, str]) -> None:
    client.post("/rooms/r_lakeside/close", headers=auth_headers)
    response = client.post("/pins/p1/comments", json={"text": "Hello"}, headers=auth_headers)
    assert response.status_code == 403


def test_add_studio_comment_cross_owner_is_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    other_headers = _second_studio_headers(client)
    response = client.post("/pins/p1/comments", json={"text": "Hello"}, headers=other_headers)
    assert response.status_code == 404
