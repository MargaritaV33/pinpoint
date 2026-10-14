"""Happy paths for each tool, against payloads shaped like openapi.yaml."""

import json

from conftest import (
    ATRIUM_EXPORT, LAKESIDE_EXPORT, TOKEN, call, image, make_client, mock_demo_rooms, pin, room,
)


def test_health_needs_no_auth(api):
    api.get("/health").respond(json={"status": "ok", "commit": "abc1234"})
    is_error, text = call(make_client(), "health")  # no credentials at all
    assert not is_error
    assert json.loads(text) == {"status": "ok", "commit": "abc1234"}
    assert "authorization" not in api.calls[0].request.headers


def test_health_commit_may_be_null(api):
    mock_demo_rooms(api)
    _, text = call(make_client(), "health")
    assert json.loads(text) == {"status": "ok", "commit": None}


def test_list_rooms_demo_account(api):
    mock_demo_rooms(api)
    is_error, text = call(make_client(token=TOKEN), "list_rooms")
    assert not is_error
    rooms = json.loads(text)
    assert [r["id"] for r in rooms] == ["r_lakeside", "r_atrium"]
    lakeside, atrium = rooms
    assert lakeside == {
        "id": "r_lakeside", "title": "Lakeside Villa — Round 2", "clientName": "Marta Lind",
        "status": "open", "createdAt": "2026-10-05T09:12:00Z", "approvedAt": None,
        "approvedBy": None, "openPinCount": 2,
    }
    assert atrium["status"] == "approved" and atrium["openPinCount"] == 0
    assert all("guestToken" not in r for r in rooms)


def test_list_rooms_empty_studio(api):
    api.get("/rooms").respond(json=[])
    _, text = call(make_client(token=TOKEN), "list_rooms")
    assert json.loads(text) == []


def test_room_summary_lakeside(api):
    mock_demo_rooms(api)
    is_error, text = call(make_client(token=TOKEN), "room_summary", room_id="r_lakeside")
    assert not is_error
    out = json.loads(text)
    assert (out["id"], out["title"], out["clientName"], out["status"]) == (
        "r_lakeside", "Lakeside Villa — Round 2", "Marta Lind", "open",
    )
    facade, living = out["images"]
    assert facade == {
        "id": "i_facade", "title": "Lake facade, golden hour", "superseded": False,
        "pins": {"fix": {"open": 1, "resolved": 0}, "question": {"open": 1, "resolved": 0}, "like": 1},
    }
    assert living["pins"] == {
        "fix": {"open": 0, "resolved": 1}, "question": {"open": 0, "resolved": 0}, "like": 1,
    }
    assert out["totals"] == {
        "fix": {"open": 1, "resolved": 1}, "question": {"open": 1, "resolved": 0}, "like": 2,
    }


def test_room_summary_empty_room(api):
    detail = {"room": room("r_new", "New", "Client", "open", "g"), "images": [], "pins": []}
    api.get("/rooms/r_new").respond(json=detail)
    _, text = call(make_client(token=TOKEN), "room_summary", room_id="r_new")
    out = json.loads(text)
    assert out["images"] == []
    assert out["totals"] == {
        "fix": {"open": 0, "resolved": 0}, "question": {"open": 0, "resolved": 0}, "like": 0,
    }


def test_room_summary_image_without_pins(api):
    detail = {
        "room": room("r_x", "X", "C", "open", "g"),
        "images": [image("i1", "r_x", "Empty view")],
        "pins": [],
    }
    api.get("/rooms/r_x").respond(json=detail)
    _, text = call(make_client(token=TOKEN), "room_summary", room_id="r_x")
    assert json.loads(text)["images"][0]["pins"]["like"] == 0


def test_room_summary_like_pin_has_null_status_and_is_counted_once(api):
    detail = {
        "room": room("r_x", "X", "C", "open", "g"),
        "images": [image("i1", "r_x", "View")],
        "pins": [pin("p1", "i1", 1, "like", None)],
    }
    api.get("/rooms/r_x").respond(json=detail)
    _, text = call(make_client(token=TOKEN), "room_summary", room_id="r_x")
    out = json.loads(text)
    assert out["totals"]["like"] == 1
    assert out["totals"]["fix"] == {"open": 0, "resolved": 0}


def test_room_summary_superseded_image_is_included_and_flagged(api):
    detail = {
        "room": room("r_x", "X", "C", "open", "g"),
        "images": [image("i_old", "r_x", "Old render", superseded=True), image("i_new", "r_x", "New render")],
        "pins": [pin("p1", "i_old", 1, "fix", "open"), pin("p2", "i_new", 1, "fix", "open")],
    }
    api.get("/rooms/r_x").respond(json=detail)
    _, text = call(make_client(token=TOKEN), "room_summary", room_id="r_x")
    out = json.loads(text)
    old, new = out["images"]
    assert old["superseded"] is True and new["superseded"] is False
    assert old["pins"]["fix"]["open"] == 1
    assert out["totals"]["fix"]["open"] == 2  # matches the backend's openPinCount


def test_open_pins_returns_export_verbatim(api):
    mock_demo_rooms(api)
    is_error, text = call(make_client(token=TOKEN), "open_pins", room_id="r_lakeside")
    assert not is_error
    assert text == LAKESIDE_EXPORT  # not parsed, not reformatted
    assert "#1 [fix]" in text and "#2 [question]" in text
    assert "[like]" not in text and "resolved" not in text


def test_open_pins_empty_room(api):
    mock_demo_rooms(api)
    _, text = call(make_client(token=TOKEN), "open_pins", room_id="r_atrium")
    assert text == ATRIUM_EXPORT
    assert "No open pins." in text


def test_approve_status_approved(api):
    mock_demo_rooms(api)
    is_error, text = call(make_client(token=TOKEN), "approve_status", room_id="r_atrium")
    assert not is_error
    assert json.loads(text) == {
        "status": "approved", "approvedAt": "2026-09-28T10:00:00Z", "approvedBy": "Jonas Berg",
    }


def test_approve_status_open(api):
    mock_demo_rooms(api)
    _, text = call(make_client(token=TOKEN), "approve_status", room_id="r_lakeside")
    assert json.loads(text) == {"status": "open", "approvedAt": None, "approvedBy": None}


def test_room_id_is_a_single_path_segment(api):
    api.get(path__regex=r"^/rooms/.*").respond(404, json={"detail": "No such room"})
    is_error, _ = call(make_client(token=TOKEN), "room_summary", room_id="a/b?c")
    assert is_error
    assert api.calls[0].request.url.raw_path == b"/rooms/a%2Fb%3Fc"
