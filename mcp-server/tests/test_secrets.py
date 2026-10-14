"""No token, password or guestToken in any result, error, log line or output."""

import logging

import httpx

from conftest import (
    ATRIUM_GUEST_TOKEN, EMAIL, LAKESIDE_GUEST_TOKEN, PASSWORD, TOKEN, call, make_client, mock_demo_rooms, session,
)

SECRETS = [TOKEN, PASSWORD, LAKESIDE_GUEST_TOKEN, ATRIUM_GUEST_TOKEN, "session-secret-token"]

ALL_CALLS = [
    ("health", {}),
    ("list_rooms", {}),
    ("room_summary", {"room_id": "r_lakeside"}),
    ("room_summary", {"room_id": "r_atrium"}),
    ("open_pins", {"room_id": "r_lakeside"}),
    ("approve_status", {"room_id": "r_atrium"}),
    ("room_summary", {"room_id": "nope"}),
]


def assert_clean(text: str) -> None:
    for secret in SECRETS:
        assert secret not in text


def run_everything(client) -> list[str]:
    return [call(client, name, **args)[1] for name, args in ALL_CALLS]


def test_no_secret_in_any_result_with_a_supplied_token(api, capsys, caplog):
    caplog.set_level(logging.DEBUG)
    mock_demo_rooms(api)
    for text in run_everything(make_client(token=TOKEN, email=EMAIL, password=PASSWORD)):
        assert_clean(text)
    out = capsys.readouterr()
    assert_clean(out.out + out.err + caplog.text)


def test_no_secret_in_any_result_with_email_password_login(api, capsys, caplog):
    caplog.set_level(logging.DEBUG)
    mock_demo_rooms(api)
    api.post("/auth/login").respond(200, json=session("session-secret-token"))
    client = make_client(email=EMAIL, password=PASSWORD)
    for text in run_everything(client):
        assert_clean(text)
    out = capsys.readouterr()
    assert_clean(out.out + out.err + caplog.text)
    assert "session-secret-token" not in repr(client)
    assert PASSWORD not in repr(client)


def test_secrets_echoed_by_a_misbehaving_backend_are_scrubbed_from_errors(api):
    api.get("/rooms/r_x").respond(404, json={"detail": f"Unknown room for token {TOKEN} and {PASSWORD}"})
    _, text = call(make_client(token=TOKEN, password=PASSWORD), "room_summary", room_id="r_x")
    assert_clean(text)
    assert "[redacted]" in text


def test_secret_not_in_connection_error_or_login_failure(api):
    api.post("/auth/login").respond(401, json={"detail": f"bad password {PASSWORD}"})
    _, text = call(make_client(email=EMAIL, password=PASSWORD), "list_rooms")
    assert_clean(text)
    api.get("/health").mock(side_effect=httpx.ConnectError(f"refused {TOKEN}"))
    _, text = call(make_client(token=TOKEN), "health")
    assert_clean(text)


def test_list_rooms_and_summary_never_expose_guest_token_even_when_present(api):
    mock_demo_rooms(api)
    for text in run_everything(make_client(token=TOKEN)):
        assert "guestToken" not in text
        assert_clean(text)
