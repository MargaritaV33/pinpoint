"""The real entry point over real stdio: it starts without touching the API,
writes only JSON-RPC to stdout, and reports a closed port from the tool call."""

import json
import os
import subprocess
import sys


def test_server_starts_against_a_closed_port_and_stdout_is_only_protocol():
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "health", "arguments": {}}},
    ]
    env = {**os.environ, "PINPOINT_BASE_URL": "http://127.0.0.1:1", "PINPOINT_TOKEN": "",
           "PINPOINT_EMAIL": "", "PINPOINT_PASSWORD": ""}
    proc = subprocess.Popen(
        [sys.executable, "-m", "pinpoint_mcp.server"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    )
    lines: list[str] = []
    try:
        for message in messages:
            proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()
        # Keep stdin open until the last answer arrives, or the server exits at EOF first.
        for line in proc.stdout:
            if line.strip():
                lines.append(line)
            if '"id":3' in line.replace(" ", ""):
                break
    finally:
        proc.stdin.close()
        try:
            rest = proc.stdout.read()
            proc.wait(timeout=30)
        finally:
            if proc.poll() is None:
                proc.kill()
        lines += [line for line in rest.splitlines() if line.strip()]
        stderr = proc.stderr.read()
    assert lines, f"no output; stderr: {stderr}"
    parsed = [json.loads(line) for line in lines]  # any non-JSON line on stdout fails here
    assert all(m.get("jsonrpc") == "2.0" for m in parsed)
    by_id = {m["id"]: m for m in parsed if "id" in m}
    assert {t["name"] for t in by_id[2]["result"]["tools"]} == {
        "health", "list_rooms", "room_summary", "open_pins", "approve_status",
    }
    health = by_id[3]["result"]
    assert health["isError"] is True
    assert "Cannot reach Pinpoint at http://127.0.0.1:1" in health["content"][0]["text"]
    assert not any("Traceback" in line for line in lines)
