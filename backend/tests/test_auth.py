from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

from app.config import settings


# -- signup -------------------------------------------------------------------

def test_signup_happy_path(client: TestClient) -> None:
    response = client.post("/auth/signup", json={"email": "new@studio.example", "password": "s3cret"})

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "new@studio.example"
    assert body["token"]


def test_signup_blank_email_is_400(client: TestClient) -> None:
    response = client.post("/auth/signup", json={"email": "   ", "password": "s3cret"})
    assert response.status_code == 400


def test_signup_invalid_email_is_400(client: TestClient) -> None:
    response = client.post("/auth/signup", json={"email": "not-an-email", "password": "s3cret"})
    assert response.status_code == 400


def test_signup_blank_password_is_400(client: TestClient) -> None:
    response = client.post("/auth/signup", json={"email": "new@studio.example", "password": ""})
    assert response.status_code == 400


def test_signup_duplicate_email_is_409(client: TestClient) -> None:
    client.post("/auth/signup", json={"email": "dup@studio.example", "password": "s3cret"})
    response = client.post("/auth/signup", json={"email": "dup@studio.example", "password": "other"})
    assert response.status_code == 409


def test_signup_seeded_demo_email_is_409(client: TestClient) -> None:
    response = client.post("/auth/signup", json={"email": "demo@pinpoint.studio", "password": "whatever"})
    assert response.status_code == 409


# -- login -------------------------------------------------------------------

def test_login_seeded_demo_credentials(client: TestClient) -> None:
    response = client.post("/auth/login", json={"email": "demo@pinpoint.studio", "password": "pinpoint"})

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["id"] == "u_demo"
    assert body["token"]


def test_login_wrong_password_is_401(client: TestClient) -> None:
    response = client.post("/auth/login", json={"email": "demo@pinpoint.studio", "password": "wrong"})
    assert response.status_code == 401


def test_login_unknown_email_is_401(client: TestClient) -> None:
    response = client.post("/auth/login", json={"email": "nobody@example.com", "password": "pinpoint"})
    assert response.status_code == 401


# -- logout --------------------------------------------------------------------

def test_logout_invalidates_the_token(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post("/auth/logout", headers=auth_headers)
    assert response.status_code == 204

    follow_up = client.get("/auth/me", headers=auth_headers)
    assert follow_up.status_code == 401


def test_validly_signed_token_without_a_session_row_is_rejected(client: TestClient) -> None:
    # A JWT signed with the server's own secret for a real user id, but never
    # issued by /auth/login or /auth/signup, so it has no row in `sessions`.
    # This is what keeps a leaked or public JWT secret from being enough to
    # impersonate a user (issue #26 audit, see security/pr-audit.md).
    now = datetime.now(timezone.utc)
    forged = jwt.encode(
        {"sub": "u_demo", "iat": now, "exp": now + timedelta(minutes=30)},
        settings.jwt_secret,
        algorithm="HS256",
    )

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"})

    assert response.status_code == 401


def test_logout_without_token_is_401(client: TestClient) -> None:
    response = client.post("/auth/logout")
    assert response.status_code == 401


# -- getCurrentUser ------------------------------------------------------------

def test_get_me_with_valid_token(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/auth/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["email"] == "demo@pinpoint.studio"


def test_get_me_without_token_is_401(client: TestClient) -> None:
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_get_me_with_malformed_token_is_401(client: TestClient) -> None:
    response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_get_me_with_expired_token_is_401(client: TestClient, monkeypatch) -> None:
    import app.auth.jwt as jwt_module

    monkeypatch.setattr(jwt_module.settings, "access_token_minutes", -1)
    login = client.post("/auth/login", json={"email": "demo@pinpoint.studio", "password": "pinpoint"})
    expired_token = login.json()["token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401
