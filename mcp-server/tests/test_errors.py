"""Every failure is a readable tool error: no crash, no traceback."""

import httpx

from conftest import BASE, EMAIL, NOT_FOUND, PASSWORD, TOKEN, call, make_client, mock_demo_rooms

TOOLS_WITH_ROOM = ["room_summary", "open_pins", "approve_status"]


def assert_readable(text: str) -> None:
    assert "Traceback" not in text and "File \"" not in text


def test_unknown_room_surfaces_the_backend_detail(api):
    mock_demo_rooms(api)
    for name in TOOLS_WITH_ROOM:
        is_error, text = call(make_client(token=TOKEN), name, room_id="nope")
        assert is_error, name
        assert "No such room, or it belongs to a different studio user." in text
        assert_readable(text)


def test_wrong_password_is_a_login_failure_naming_email_without_echoing_it(api):
    login = api.post("/auth/login").respond(401, json={"detail": "Invalid email or password"})
    is_error, text = call(make_client(email=EMAIL, password=PASSWORD), "list_rooms")
    assert is_error
    assert "Login" in text and "PINPOINT_EMAIL" in text
    assert PASSWORD not in text
    assert login.call_count == 1  # a failed login is not retried


def test_connection_refused_says_cannot_reach_and_hints_make_up(api):
    api.get("/rooms").mock(side_effect=httpx.ConnectError("[Errno 111] Connection refused"))
    is_error, text = call(make_client(token=TOKEN), "list_rooms")
    assert is_error
    assert f"Cannot reach Pinpoint at {BASE}" in text
    assert "make up" in text
    assert_readable(text)


def test_timeout_says_cannot_reach(api):
    api.get("/health").mock(side_effect=httpx.ReadTimeout("timed out"))
    is_error, text = call(make_client(), "health")
    assert is_error and "Cannot reach Pinpoint" in text


def test_requests_have_a_10_second_timeout(api):
    seen = []
    api.get("/health").mock(
        side_effect=lambda request: seen.append(request.extensions["timeout"]) or httpx.Response(200, json={"status": "ok"})
    )
    call(make_client(), "health")
    assert seen == [{"connect": 10.0, "read": 10.0, "write": 10.0, "pool": 10.0}]


def test_5xx_reports_the_status_code(api):
    api.get("/rooms").respond(502, text="<html>Bad gateway\nTraceback (most recent call last)...</html>")
    is_error, text = call(make_client(token=TOKEN), "list_rooms")
    assert is_error and "502" in text
    assert_readable(text)  # the raw body is not forwarded


def test_json_5xx_reports_the_status_code(api):
    api.get("/rooms/r_x").respond(500, json={"detail": "boom"})
    is_error, text = call(make_client(token=TOKEN), "room_summary", room_id="r_x")
    assert is_error and "500" in text


def test_non_json_success_body_is_reported_with_the_status(api):
    api.get("/rooms").respond(200, text="<html>not json</html>", headers={"content-type": "text/html"})
    is_error, text = call(make_client(token=TOKEN), "list_rooms")
    assert is_error and "200" in text and "not valid JSON" in text


def test_unexpected_json_shape_is_reported_not_crashed(api):
    api.get("/rooms/r_x").respond(200, json={"unexpected": True})
    for name in ("room_summary", "approve_status"):
        is_error, text = call(make_client(token=TOKEN), name, room_id="r_x")
        assert is_error and "unexpected shape" in text
        assert_readable(text)


def test_non_json_health_is_reported(api):
    api.get("/health").respond(200, text="OK")
    is_error, text = call(make_client(), "health")
    assert is_error and "200" in text


def test_other_4xx_without_detail(api):
    api.get("/rooms").respond(403, text="forbidden")
    is_error, text = call(make_client(token=TOKEN), "list_rooms")
    assert is_error and "403" in text


def test_not_found_json_is_the_documented_error_shape():
    assert NOT_FOUND == {"detail": "No such room, or it belongs to a different studio user."}
