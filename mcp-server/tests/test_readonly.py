"""The read-only guarantee, enforced by tests rather than by promise."""

import asyncio

import httpx
from mcp.shared.memory import create_connected_server_and_client_session

from conftest import EMAIL, PASSWORD, TOKEN, call, make_client, mock_demo_rooms, requests_made, session
from pinpoint_mcp.server import build_server

EXPECTED_TOOLS = {"health", "list_rooms", "room_summary", "open_pins", "approve_status"}
ROOM_TOOLS = {"room_summary", "open_pins", "approve_status"}


def _list_tools():
    async def run():
        server = build_server(make_client())
        async with create_connected_server_and_client_session(server._mcp_server) as client:
            tools = await client.list_tools()
            return server, tools.tools

    return asyncio.run(run())


def test_exactly_the_five_tools_are_registered():
    _, tools = _list_tools()
    assert {t.name for t in tools} == EXPECTED_TOOLS
    assert len(tools) == 5


def test_every_tool_is_annotated_read_only():
    _, tools = _list_tools()
    for tool in tools:
        assert tool.annotations is not None, tool.name
        assert tool.annotations.readOnlyHint is True, tool.name
        assert tool.annotations.destructiveHint is False, tool.name


def test_server_instructions_say_read_only_and_name_what_it_never_does():
    server, _ = _list_tools()
    text = server.instructions.lower()
    assert "read-only" in text
    for verb in ("creates", "resolves", "replies to", "approves", "closes", "deletes"):
        assert verb in text, verb


def test_each_tool_has_a_description_and_room_tools_describe_room_id():
    _, tools = _list_tools()
    for tool in tools:
        assert tool.description and len(tool.description) > 20, tool.name
        if tool.name in ROOM_TOOLS:
            desc = tool.inputSchema["properties"]["room_id"]["description"]
            assert desc.lower() == "a room id from `list_rooms`."
            assert tool.inputSchema["required"] == ["room_id"]
        else:
            assert tool.inputSchema.get("properties", {}) == {}


def test_approve_status_description_explains_reopening_and_closed():
    _, tools = _list_tools()
    desc = next(t for t in tools if t.name == "approve_status").description
    assert "approved" in desc and "open" in desc and "new fix or question pin" in desc
    assert "closed" in desc


def test_every_request_across_all_tools_is_a_get_except_the_login_post(api):
    mock_demo_rooms(api)
    api.post("/auth/login").respond(200, json=session("tok"))
    # Success paths, with login, then error paths (404, 401 re-login, unreachable).
    client = make_client(email=EMAIL, password=PASSWORD)
    for name, args in [
        ("health", {}), ("list_rooms", {}),
        ("room_summary", {"room_id": "r_lakeside"}), ("open_pins", {"room_id": "r_atrium"}),
        ("approve_status", {"room_id": "r_atrium"}),
        ("room_summary", {"room_id": "nope"}), ("open_pins", {"room_id": "nope"}),
    ]:
        call(client, name, **args)
    api.get("/rooms").mock(side_effect=httpx.ConnectError("refused"))
    call(client, "list_rooms")
    api.get("/rooms").respond(401, json={"detail": "expired"})
    call(client, "list_rooms")  # triggers re-login + retry
    call(make_client(token=TOKEN), "list_rooms")  # token 401, no retry
    call(make_client(), "list_rooms")  # no credentials

    made = requests_made(api)
    assert made, "no requests recorded"
    assert ("POST", "/auth/login") in made  # the one allowed exception was exercised
    assert all(
        method == "GET" or (method, path) == ("POST", "/auth/login") for method, path in made
    )
    assert not any(path.startswith("/guest") or path == "/auth/logout" for _, path in made)
    # The client's own log agrees (this is what the integration test checks too).
    assert all(m == "GET" or (m, p) == ("POST", "/auth/login") for m, p in client.request_log)


def test_client_module_can_only_issue_get_and_login_post():
    import inspect

    from pinpoint_mcp import client as client_module

    source = inspect.getsource(client_module)
    for method in ("PATCH", "PUT", "DELETE"):
        assert f'"{method}"' not in source
    assert "/guest" not in source and "/auth/logout" not in source
