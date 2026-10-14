"""Configuration and login: precedence, re-login, empty-as-unset, base URL."""

import json

import httpx

from conftest import (
    BASE, EMAIL, LAKESIDE, PASSWORD, TOKEN, call, make_client, mock_demo_rooms, requests_made, session, summary,
)
from pinpoint_mcp.client import DEFAULT_BASE_URL, PinpointClient


def bearer(call_) -> str:
    return call_.request.headers["authorization"]


def test_token_is_sent_as_bearer_and_wins_over_email_password(api):
    mock_demo_rooms(api)
    client = make_client(token=TOKEN, email=EMAIL, password=PASSWORD)
    is_error, _ = call(client, "list_rooms")
    assert not is_error
    assert requests_made(api) == [("GET", "/rooms")]  # no login attempted
    assert bearer(api.calls[0]) == f"Bearer {TOKEN}"


def test_email_password_logs_in_once_and_reuses_the_token(api):
    mock_demo_rooms(api)
    login = api.post("/auth/login").respond(201, json=session("session-token-1"))
    client = make_client(email=EMAIL, password=PASSWORD)
    for _ in range(2):
        is_error, _ = call(client, "list_rooms")
        assert not is_error
    assert login.call_count == 1  # token kept in memory between calls
    assert json.loads(login.calls[0].request.content) == {"email": EMAIL, "password": PASSWORD}
    gets = [c for c in api.calls if c.request.method == "GET"]
    assert {bearer(c) for c in gets} == {"Bearer session-token-1"}


def test_expired_session_logs_in_again_once_and_retries_once(api):
    tokens = iter(["old-token", "new-token"])
    api.post("/auth/login").mock(side_effect=lambda request: httpx.Response(200, json=session(next(tokens))))
    api.get("/rooms").mock(
        side_effect=lambda request: (
            httpx.Response(401, json={"detail": "Invalid or expired token"})
            if request.headers["authorization"] == "Bearer old-token"
            else httpx.Response(200, json=[summary(LAKESIDE, 2)])
        )
    )
    is_error, text = call(make_client(email=EMAIL, password=PASSWORD), "list_rooms")
    assert not is_error
    assert json.loads(text)[0]["id"] == "r_lakeside"
    assert requests_made(api) == [
        ("POST", "/auth/login"), ("GET", "/rooms"), ("POST", "/auth/login"), ("GET", "/rooms"),
    ]


def test_second_401_after_fresh_login_is_not_retried_again(api):
    login = api.post("/auth/login").respond(200, json=session("tok"))
    rooms = api.get("/rooms").respond(401, json={"detail": "nope"})
    is_error, text = call(make_client(email=EMAIL, password=PASSWORD), "list_rooms")
    assert is_error
    assert login.call_count == 2 and rooms.call_count == 2
    assert "PINPOINT_EMAIL" in text


def test_supplied_token_401_is_reported_and_never_retried(api):
    rooms = api.get("/rooms").respond(401, json={"detail": "Invalid or expired token"})
    client = make_client(token=TOKEN, email=EMAIL, password=PASSWORD)  # pair is ignored: token wins
    is_error, text = call(client, "list_rooms")
    assert is_error
    assert rooms.call_count == 1
    assert ("POST", "/auth/login") not in requests_made(api)
    assert "PINPOINT_TOKEN" in text and "expired or invalid" in text


def test_no_credentials_names_the_variables_but_health_still_works(api):
    mock_demo_rooms(api)
    client = make_client()
    for name, args in [
        ("list_rooms", {}), ("room_summary", {"room_id": "r_lakeside"}),
        ("open_pins", {"room_id": "r_lakeside"}), ("approve_status", {"room_id": "r_lakeside"}),
    ]:
        is_error, text = call(client, name, **args)
        assert is_error, name
        assert "PINPOINT_TOKEN" in text and "PINPOINT_EMAIL" in text and "PINPOINT_PASSWORD" in text
    assert requests_made(api) == []  # nothing was sent without credentials
    is_error, _ = call(client, "health")
    assert not is_error


def test_half_a_pair_counts_as_no_credentials(api):
    mock_demo_rooms(api)
    for kwargs in ({"email": EMAIL}, {"password": PASSWORD}):
        is_error, text = call(make_client(**kwargs), "list_rooms")
        assert is_error and "PINPOINT_EMAIL" in text
    assert requests_made(api) == []


def test_empty_strings_count_as_unset():
    env = {
        "PINPOINT_BASE_URL": "", "PINPOINT_TOKEN": "", "PINPOINT_EMAIL": "", "PINPOINT_PASSWORD": "",
    }
    client = PinpointClient.from_env(env)
    assert client.base_url == DEFAULT_BASE_URL == "http://localhost:8100"
    assert client.token == "" and not client.uses_login


def test_empty_token_falls_through_to_email_password(api):
    mock_demo_rooms(api)
    api.post("/auth/login").respond(200, json=session("from-login"))
    client = PinpointClient.from_env(
        {"PINPOINT_BASE_URL": BASE, "PINPOINT_TOKEN": "", "PINPOINT_EMAIL": EMAIL, "PINPOINT_PASSWORD": PASSWORD}
    )
    is_error, _ = call(client, "list_rooms")
    assert not is_error
    assert bearer(api.calls[-1]) == "Bearer from-login"


def test_from_env_reads_all_four_variables():
    client = PinpointClient.from_env(
        {"PINPOINT_BASE_URL": "http://x:1", "PINPOINT_TOKEN": "t", "PINPOINT_EMAIL": "e", "PINPOINT_PASSWORD": "p"}
    )
    assert (client.base_url, client.token, client.email, client.password) == ("http://x:1", "t", "e", "p")


def test_base_url_defaults_when_unset():
    assert PinpointClient.from_env({}).base_url == "http://localhost:8100"


def test_trailing_slash_in_base_url_is_tolerated(api):
    mock_demo_rooms(api)
    client = make_client(base_url=f"{BASE}/", token=TOKEN)
    is_error, _ = call(client, "list_rooms")
    assert not is_error
    assert str(api.calls[0].request.url) == f"{BASE}/rooms"  # no //rooms
    assert PinpointClient(base_url="http://localhost:8091///").base_url == "http://localhost:8091"
