"""Auth: signup, login, me, logout, and token revocation on logout.

Each test signs up its own studio user (unique email) so it is independent
of run order and of every other test in this suite.
"""

from __future__ import annotations

import httpx

from conftest import auth_headers, signup, unique_email


def test_signup_then_login_then_me_then_logout_revokes_token(client: httpx.Client) -> None:
    email = unique_email()
    password = "testpass123"

    signup_response = signup(client, email=email, password=password)
    assert signup_response.status_code == 201, signup_response.text
    session = signup_response.json()
    assert session["token"]
    assert session["user"]["email"] == email

    login_response = client.post("/auth/login", json={"email": email, "password": password})
    assert login_response.status_code == 200, login_response.text
    login_session = login_response.json()
    token = login_session["token"]
    assert token

    me_response = client.get("/auth/me", headers=auth_headers(token))
    assert me_response.status_code == 200, me_response.text
    assert me_response.json()["email"] == email

    logout_response = client.post("/auth/logout", headers=auth_headers(token))
    assert logout_response.status_code == 204, logout_response.text

    # Revocation, not just JWT expiry: the same token is rejected immediately.
    me_again_response = client.get("/auth/me", headers=auth_headers(token))
    assert me_again_response.status_code == 401, me_again_response.text
