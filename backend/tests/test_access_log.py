"""Tests for the JSON access log and the X-Request-Id header (issue #38, part 5).

The access log is one JSON object per request on stdout. The tests read it with
`capsys` (the handler looks `sys.stdout` up on every write, so capsys sees it)
and parse every line, so a stray non-JSON line or a second line per request
fails them. See `ops/observability.md` for the format.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import app.main as main_module
from app.access_log import UNMATCHED_PATH, is_valid_request_id
from app.main import app

FIELDS = {"ts", "level", "request_id", "method", "path", "status", "duration_ms"}
GENERATED_ID = re.compile(r"[0-9a-f]{32}")


def access_lines(capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    out = capsys.readouterr().out
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def one_line(capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    lines = access_lines(capsys)
    assert len(lines) == 1, lines
    return lines[0]


@pytest.fixture()
def frontend_dist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    dist = tmp_path / "frontend_dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "_shell.html").write_text("<html><body>shell</body></html>")
    (dist / "assets" / "app.abc123.js").write_text("console.log('hi');")
    monkeypatch.setattr(main_module, "FRONTEND_DIST", dist)
    return dist


@pytest.fixture()
def boom_route() -> Iterator[None]:
    """A route that raises, to exercise the unhandled-exception (500) path.
    Added in front of the SPA catch-all for the duration of one test."""

    def boom(token: str) -> None:
        raise RuntimeError("secret-in-exception-message")

    route = APIRoute("/_test/boom/{token}", boom, methods=["GET"], include_in_schema=False)
    app.router.routes.insert(0, route)
    yield
    app.router.routes.remove(route)


# -- the log line ------------------------------------------------------------------


def test_health_is_logged_as_one_json_line_with_typed_fields(client: TestClient, capsys: pytest.CaptureFixture[str]) -> None:
    capsys.readouterr()  # drop anything printed by fixtures

    response = client.get("/health")

    line = one_line(capsys)
    assert set(line) == FIELDS
    assert isinstance(line["ts"], str)
    parsed = datetime.fromisoformat(line["ts"])
    assert parsed.utcoffset() == timedelta(0)
    assert line["level"] == "INFO"
    assert line["request_id"] == response.headers["X-Request-Id"]
    assert line["method"] == "GET"
    assert line["path"] == "/health"
    assert line["status"] == 200 and isinstance(line["status"], int)
    assert isinstance(line["duration_ms"], (int, float)) and not isinstance(line["duration_ms"], bool)
    assert line["duration_ms"] >= 0
    assert round(line["duration_ms"], 3) == line["duration_ms"]


def test_path_is_the_route_template_not_the_concrete_url(
    client: TestClient, auth_headers: dict[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()

    response = client.get("/rooms/r_lakeside", headers=auth_headers)

    assert response.status_code == 200
    line = one_line(capsys)
    assert line["path"] == "/rooms/{roomId}"
    assert "r_lakeside" not in json.dumps(line)


# -- secrets never reach the log -----------------------------------------------------


def test_guest_token_and_query_string_are_not_logged(client: TestClient, capsys: pytest.CaptureFixture[str]) -> None:
    capsys.readouterr()

    response = client.get("/guest/lakeside-demo?token=secret-query-value&x=1")

    assert response.status_code == 200
    out = capsys.readouterr().out
    line = json.loads(out)
    assert line["path"] == "/guest/{guestToken}"
    assert "lakeside-demo" not in out
    assert "secret-query-value" not in out
    assert "token=" not in out and "?" not in out


def test_guest_token_in_a_nested_route_is_not_logged(client: TestClient, capsys: pytest.CaptureFixture[str]) -> None:
    capsys.readouterr()

    response = client.post(
        "/guest/lakeside-demo/pins?token=secret-query-value",
        json={"imageId": "i_facade", "x": 10.0, "y": 20.0, "type": "fix", "text": "body text must not be logged", "authorName": "Marta"},
    )

    assert response.status_code == 201
    out = capsys.readouterr().out
    assert json.loads(out)["path"] == "/guest/{guestToken}/pins"
    for leaked in ("lakeside-demo", "secret-query-value", "body text must not be logged", "Marta"):
        assert leaked not in out


def test_studio_bearer_token_is_not_logged(
    client: TestClient, studio_token: str, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()

    response = client.get("/rooms", headers={"Authorization": f"Bearer {studio_token}", "Cookie": "session=cookie-secret"})

    assert response.status_code == 200
    out = capsys.readouterr().out
    assert json.loads(out)["path"] == "/rooms"
    assert studio_token not in out
    assert "Bearer" not in out and "cookie-secret" not in out


def test_login_body_is_not_logged(client: TestClient, capsys: pytest.CaptureFixture[str]) -> None:
    capsys.readouterr()

    client.post("/auth/login", json={"email": "demo@pinpoint.studio", "password": "pinpoint"})

    out = capsys.readouterr().out
    assert "demo@pinpoint.studio" not in out
    assert '"password"' not in out


def test_unmatched_path_is_a_fixed_placeholder_not_the_raw_path(client: TestClient, capsys: pytest.CaptureFixture[str]) -> None:
    capsys.readouterr()

    response = client.get("/pins/typed-token-lakeside-demo/nowhere?token=secret-query-value")

    assert response.status_code == 404
    out = capsys.readouterr().out
    assert json.loads(out)["path"] == UNMATCHED_PATH == "unmatched"
    assert "typed-token-lakeside-demo" not in out and "secret-query-value" not in out


# -- request id ----------------------------------------------------------------------


def test_request_without_id_gets_a_fresh_one_each_time(client: TestClient, capsys: pytest.CaptureFixture[str]) -> None:
    capsys.readouterr()

    first = client.get("/health").headers["X-Request-Id"]
    second = client.get("/health").headers["X-Request-Id"]

    assert GENERATED_ID.fullmatch(first) and GENERATED_ID.fullmatch(second)
    assert first != second
    assert [l["request_id"] for l in access_lines(capsys)] == [first, second]


def test_valid_incoming_id_is_echoed_and_logged(client: TestClient, capsys: pytest.CaptureFixture[str]) -> None:
    capsys.readouterr()

    response = client.get("/health", headers={"X-Request-Id": "trace.123_abc-DEF"})

    assert response.headers["X-Request-Id"] == "trace.123_abc-DEF"
    assert one_line(capsys)["request_id"] == "trace.123_abc-DEF"


def test_64_character_id_is_accepted(client: TestClient) -> None:
    assert client.get("/health", headers={"X-Request-Id": "a" * 64}).headers["X-Request-Id"] == "a" * 64


@pytest.mark.parametrize(
    "bad",
    ["a" * 65, "has space", "tab\there", "quote\"", "{braces}", "semi;colon", "slash/slash", "\x01ctl", ""],
    ids=["65-chars", "space", "tab", "quote", "braces", "semicolon", "slash", "control-char", "empty"],
)
def test_invalid_incoming_id_is_replaced_never_echoed_or_logged(
    client: TestClient, capsys: pytest.CaptureFixture[str], bad: str
) -> None:
    capsys.readouterr()

    response = client.get("/health", headers={"X-Request-Id": bad})

    assert response.status_code == 200
    returned = response.headers["X-Request-Id"]
    assert GENERATED_ID.fullmatch(returned)
    out = capsys.readouterr().out
    assert json.loads(out)["request_id"] == returned
    if bad:
        assert bad not in out


def test_non_ascii_incoming_id_is_replaced(client: TestClient, capsys: pytest.CaptureFixture[str]) -> None:
    capsys.readouterr()

    response = client.get("/health", headers=[(b"x-request-id", "marker-café".encode("utf-8"))])

    assert GENERATED_ID.fullmatch(response.headers["X-Request-Id"])
    assert "marker-caf" not in capsys.readouterr().out


@pytest.mark.parametrize("good", ["a", "A", "0", "a.b", "a_b", "a-b", "a" * 64, "550e8400-e29b-41d4-a716-446655440000"])
def test_validator_accepts(good: str) -> None:
    assert is_valid_request_id(good)


@pytest.mark.parametrize(
    "bad",
    [None, "", "a" * 65, "a b", "abc\n", "abc\r\n", "\nabc", "a\nb", "abc\x00", "café", "a'b", "a\"b", "{a}", "a/b", "a;b", "١٢"],
    ids=repr,
)
def test_validator_rejects(bad: str | None) -> None:
    # `abc\n` is the case a `^...$` regex would let through: `$` matches before
    # a trailing newline. The validator must use fullmatch.
    assert not is_valid_request_id(bad)


# -- the id is on every response -----------------------------------------------------


def test_404_has_the_id_and_is_logged(client: TestClient, capsys: pytest.CaptureFixture[str]) -> None:
    capsys.readouterr()

    response = client.get("/pins")

    assert response.status_code == 404
    line = one_line(capsys)
    assert line["status"] == 404
    assert line["path"] == "unmatched"
    assert line["request_id"] == response.headers["X-Request-Id"]


def test_401_and_422_carry_the_id(client: TestClient, capsys: pytest.CaptureFixture[str]) -> None:
    capsys.readouterr()

    unauthorized = client.get("/rooms")
    invalid = client.post("/auth/login", json={"email": 123})

    assert unauthorized.status_code == 401
    assert invalid.status_code == 422
    lines = access_lines(capsys)
    assert [l["status"] for l in lines] == [401, 422]
    assert [l["request_id"] for l in lines] == [unauthorized.headers["X-Request-Id"], invalid.headers["X-Request-Id"]]
    assert lines[1]["path"] == "/auth/login"


def test_wrong_method_405_carries_the_id(client: TestClient, capsys: pytest.CaptureFixture[str]) -> None:
    capsys.readouterr()

    response = client.delete("/health")

    assert response.status_code == 405
    assert one_line(capsys)["request_id"] == response.headers["X-Request-Id"]


def test_cors_preflight_carries_the_id(client: TestClient) -> None:
    response = client.options(
        "/rooms",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )

    assert response.status_code == 200
    assert GENERATED_ID.fullmatch(response.headers["X-Request-Id"])


def test_spa_fallback_and_static_file_carry_the_id_and_log_the_placeholder(
    client: TestClient, frontend_dist: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()

    shell = client.get("/rooms-typed-token-xyz/deep/link?token=secret-query-value")
    asset = client.get("/assets/app.abc123.js")

    assert shell.status_code == 200 and "shell" in shell.text
    assert asset.status_code == 200 and "console.log" in asset.text
    out = capsys.readouterr().out
    lines = [json.loads(l) for l in out.splitlines()]
    assert [l["path"] for l in lines] == ["unmatched", "unmatched"]
    assert [l["request_id"] for l in lines] == [shell.headers["X-Request-Id"], asset.headers["X-Request-Id"]]
    assert "typed-token-xyz" not in out and "secret-query-value" not in out and "app.abc123" not in out


def test_unhandled_exception_is_logged_once_as_500_with_the_id_and_no_traceback(
    boom_route: None, capsys: pytest.CaptureFixture[str]
) -> None:
    # raise_server_exceptions=False: get the 500 response instead of the re-raised error.
    client = TestClient(app, raise_server_exceptions=False)
    capsys.readouterr()

    response = client.get("/_test/boom/some-token?x=secret-query-value")

    assert response.status_code == 500
    out = capsys.readouterr().out
    assert len(out.strip().splitlines()) == 1
    line = json.loads(out)
    assert set(line) == FIELDS
    assert line["status"] == 500
    assert line["level"] == "ERROR"
    assert line["path"] == "/_test/boom/{token}"
    assert line["request_id"] == response.headers["X-Request-Id"]
    for leaked in ("Traceback", "RuntimeError", "secret-in-exception-message", "some-token", "secret-query-value"):
        assert leaked not in out


def test_unhandled_exception_still_propagates_to_the_server(boom_route: None) -> None:
    # The middleware logs and re-raises: uvicorn keeps writing the traceback to
    # its own error log, and the default test client still sees the exception.
    with pytest.raises(RuntimeError):
        TestClient(app).get("/_test/boom/x")


def test_uvicorns_own_access_log_is_off_because_it_prints_the_full_url() -> None:
    # `"GET /guest/<token>?x=1 HTTP/1.1" 200` would put the token in the log
    # next to our sanitised line. Importing the app switches that logger off.
    assert logging.getLogger("uvicorn.access").disabled is True
