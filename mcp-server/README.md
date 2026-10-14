# Pinpoint MCP server

A small, **read-only** [MCP](https://modelcontextprotocol.io) server that lets an
AI assistant (Claude Code first, any MCP client second) ask a *running* Pinpoint
instance questions about a studio's rooms, for example "how many open fix pins
are in each demo room?". It talks to Pinpoint's existing HTTP API over stdio. It
changes nothing in Pinpoint's backend, frontend or contract, and nothing in
Pinpoint can be changed through it.

It is a self-contained uv project (own `pyproject.toml`, own `uv.lock`); nothing
here is installed by `backend/`, `integration/` or the repo root.

## Tools

Exactly five, each annotated `readOnlyHint=True`. The server's instructions say
that no tool creates, resolves, replies to, approves, closes or deletes anything,
and a unit test fails if that sentence or an annotation goes missing.

| Tool | Backed by | What it returns |
|---|---|---|
| `health()` | `GET /health` (no auth) | JSON `status` and `commit`. |
| `list_rooms()` | `GET /rooms` | JSON list: `id`, `title`, `clientName`, `status` (`open`/`approved`/`closed`), `createdAt`, `approvedAt`, `approvedBy`, `openPinCount`. Never `guestToken`. |
| `room_summary(room_id)` | `GET /rooms/{roomId}` | JSON: room `id`, `title`, `clientName`, `status`; `images` (each `id`, `title`, `superseded`, own pin counts); room-wide `totals`. Counts look like `{"fix": {"open": n, "resolved": n}, "question": {"open": n, "resolved": n}, "like": n}` (`like` pins have no status). Superseded images are included and flagged, because the backend's `openPinCount` and the export count them too. |
| `open_pins(room_id)` | `GET /rooms/{roomId}/export` | The backend's `text/plain` export of open fix and question pins, grouped by image, **verbatim** (not parsed). `No open pins.` when there are none. |
| `approve_status(room_id)` | `GET /rooms/{roomId}` | JSON `status`, `approvedAt`, `approvedBy` of the room. There is no dedicated endpoint; `approved` goes back to `open` when a client adds a new fix or question pin after approval, and `closed` is a separate state. |

`room_id` is "a room id from `list_rooms`". There is no per-image or per-pin list
endpoint in Pinpoint's contract, which is why `room_summary` and `approve_status`
both read the room detail.

## Configuration

Environment variables only; nothing is hard-coded.

| Variable | Default | Meaning |
|---|---|---|
| `PINPOINT_BASE_URL` | `http://localhost:8100` | Where Pinpoint listens. A trailing slash is fine. |
| `PINPOINT_TOKEN` | unset | A studio bearer token. If set and non-empty it is sent as `Authorization: Bearer <token>` and nothing else is tried. |
| `PINPOINT_EMAIL`, `PINPOINT_PASSWORD` | unset | If no token is set and both are non-empty, the server calls `POST /auth/login` itself and keeps the session token in memory only. |

Empty strings count as unset, so an unexpanded `${VAR:-}` in `.mcp.json` is
harmless. With no token and no complete email/password pair, every authenticated
tool returns an error naming `PINPOINT_TOKEN` and `PINPOINT_EMAIL` /
`PINPOINT_PASSWORD`; `health()` still works.

Studio tokens expire (`ACCESS_TOKEN_MINUTES`, default 60). When the server logged
in itself and gets a 401, it logs in again once and retries that call once. With
`PINPOINT_TOKEN` a 401 is reported as an expired or invalid token and never
retried.

**Ports.** `make up` (Docker Compose) serves Pinpoint on `8100`, which is the
default here. `make run` (uvicorn on the host) listens on **`8091`**, so against
`make run` set `PINPOINT_BASE_URL=http://localhost:8091`. The first `servers`
entry in `openapi.yaml` (`8000`) is what neither command uses.

The token, the password and every `guestToken` never appear in a tool result, an
error message, a log line or test output (tests assert this). Errors are readable
tool errors, never tracebacks: unknown room (the backend's 404 `detail`), a wrong
email/password (names `PINPOINT_EMAIL`, never echoes the password), an
unreachable backend ("Cannot reach Pinpoint at <url>", with a hint to run
`make up`; requests time out after 10 s), and non-JSON or 5xx responses (with the
status code).

## Dependencies

All declared in `pyproject.toml` and nowhere else.

| Dependency | Why |
|---|---|
| `mcp` (`>=1.12,<2`) | The official MCP SDK: provides FastMCP and the stdio transport. Pinned below 2 because FastMCP is what this project is specified against; `mcp` 2.x renamed it to `MCPServer` and changed other APIs, so moving to 2.x is a separate, deliberate task. |
| `httpx` | The HTTP client. Declared explicitly although `mcp` depends on it, because this project imports it directly. |
| `pytest` (dev) | Test runner. |
| `respx` (dev) | Mocks httpx, so the unit tests need no network, backend or Docker. |

`pytest-asyncio` is not needed: tests drive the tools through the real MCP
protocol (an in-memory session) from plain synchronous test functions. The build
backend is `hatchling` (a build-time tool, not a runtime dependency), so that
`pinpoint-mcp` installs as a console script.

## Run it

```bash
cd mcp-server && uv sync --frozen           # from a clean checkout
uv run --directory mcp-server pinpoint-mcp   # from the repo root; waits for an MCP client on stdio
```

The server does not call the API at startup, so it starts even when
`PINPOINT_BASE_URL` points at a closed port; the failure shows up in the tool
call. stdout carries only protocol messages; logs go to stderr.

### In Claude Code

The repo-root `.mcp.json` registers the server as `pinpoint` with exactly
`uv run --directory mcp-server pinpoint-mcp`. The `--directory` path is
relative, so **start Claude Code in the repo root**. Claude Code asks once to
approve a project-scoped `.mcp.json` server.

Against the Compose stack and the seeded demo account (the credentials are
public in the repo `README.md`):

```bash
make up
export PINPOINT_EMAIL=demo@pinpoint.studio PINPOINT_PASSWORD=pinpoint
claude        # in the repo root; approve the "pinpoint" server when asked
# then ask: how many open fix pins are in each demo room?
make down
```

`.mcp.json` contains no token, password or email value; it passes the four
variables through `${VAR:-default}` expansion.

### Other assistants

Same command, same environment variables, different file. **None of these were
run here ("not tested here")**; they are the standard shapes of each client's
config, filled in with this server's command.

Claude Desktop, `claude_desktop_config.json` (needs an absolute `--directory`
path, and does not expand `${VAR}`, so values are literal in that local file;
never commit it with real credentials). Not tested here:

```json
{
  "mcpServers": {
    "pinpoint": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/pinpoint/mcp-server", "pinpoint-mcp"],
      "env": {
        "PINPOINT_BASE_URL": "http://localhost:8100",
        "PINPOINT_EMAIL": "demo@pinpoint.studio",
        "PINPOINT_PASSWORD": "pinpoint"
      }
    }
  }
}
```

Cursor (`.cursor/mcp.json`) and other clients that read an `mcpServers` object use
the same entry as above. Not tested here.

VS Code (`.vscode/mcp.json`) wraps it in `servers` and names the transport. Not
tested here:

```json
{
  "servers": {
    "pinpoint": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/pinpoint/mcp-server", "pinpoint-mcp"],
      "env": { "PINPOINT_BASE_URL": "http://localhost:8100" }
    }
  }
}
```

Codex-style clients use the same command and variables; the file format differs
(Codex reads TOML from `~/.codex/config.toml`), so translate the entry
accordingly. Not tested here.

## Tests

```bash
make mcp-test                        # from the repo root; same as: cd mcp-server && uv run pytest
cd mcp-server && uv run pytest -rs   # -rs shows why the integration test was skipped
```

The unit tests mock HTTP with `respx` and need no backend, no network and no
Docker. They cover each tool's happy path on payloads shaped like the
`RoomSummary`, `RoomDetail` and `Session` schemas, token precedence, login and
the single re-login on 401, empty-string-as-unset, a trailing-slash base URL, an
empty room, a `like` pin with `status: null`, a superseded image, every error
case, a GET-only assertion over every request on success and error paths (the
one exception is `POST /auth/login`), the read-only description and annotations,
that no secret or `guestToken` appears in any result, and the real entry point
over stdio against a closed port.

`tests/test_integration.py` talks to a real stack. It is **skipped** (visibly,
with a reason) unless `PINPOINT_BASE_URL` is set:

```bash
make up
cd mcp-server && PINPOINT_BASE_URL=http://localhost:8100 uv run pytest tests/test_integration.py -v
make down
```

It uses `PINPOINT_EMAIL` / `PINPOINT_PASSWORD` if set, else the seeded demo
account, and ignores `PINPOINT_TOKEN` so that it exercises the login path. It
asserts the seed as it stands: `health()` is `ok`, both demo rooms are listed,
`room_summary("r_lakeside")` has 1 open fix, `open_pins("r_atrium")` contains
`No open pins.`, `approve_status("r_atrium")` is `approved`, and only GET
requests plus the login POST were issued.

## CI

`.github/workflows/ci.yml` has an `mcp` job: Python 3.12 and uv exactly as the
`backend` job, `uv sync --frozen`, `uv run pytest -rs`. No Postgres, no Docker,
no `needs`. The integration test shows as skipped in its log. Running it against
the Compose stack in CI is tracked separately (#21).

`mcp` is deliberately **not** in `stack.needs` or `deploy.needs`. Like
`agents-sync` (#18) it checks something that is not in the deployed image (the
`Dockerfile` copies only `backend/`, `frontend/` and `openapi.yaml`), so a red
`mcp` cannot change what ships, and it still shows as a failing check on the
commit. Gating the deploy on it is a one-line change to `deploy.needs`; that is
the owner's decision.

## Live demo transcript

A real, unedited run. Date: 2026-10-14. Repository commit: `8f64914`
(`git rev-parse --short HEAD`, clean working tree). Stack: `make up` (Docker
Compose, fresh volumes, seed data). Client: Claude Code 2.1.299, model
`claude-sonnet-5-5`, a fresh headless session started from the repo root so the
project `.mcp.json` was picked up.

Command (the demo account is the public seed account from the repo `README.md`;
`--settings` approves the project-scoped server, which a headless run cannot
click through):

```bash
export PINPOINT_EMAIL=demo@pinpoint.studio PINPOINT_PASSWORD=pinpoint
claude -p "how many open fix pins are in each demo room?" \
  --settings '{"enabledMcpjsonServers":["pinpoint"]}' \
  --allowedTools "mcp__pinpoint__*" \
  --output-format stream-json --verbose > run.jsonl
python mcp-server/scripts/render_transcript.py "how many open fix pins are in each demo room?" < run.jsonl
```

`render_transcript.py` only lays the events out; it drops the `system` init event
(a list of every MCP server on the machine), rate-limit events and empty
encrypted `thinking` blocks, and changes no text. No token, password or
`guestToken` appeared anywhere in the run (checked by searching the raw output),
so nothing was replaced by `[redacted]`. The first `ToolSearch` call is Claude
Code loading the deferred MCP tool schemas, as it happened.

```text
PROMPT: how many open fix pins are in each demo room?

TOOL CALL: ToolSearch {"query": "select:mcp__pinpoint__list_rooms,mcp__pinpoint__room_summary,mcp__pinpoint__open_pins,mcp__pinpoint__health", "max_results": 4}

TOOL RESULT:
{"type": "tool_reference", "tool_name": "mcp__pinpoint__list_rooms"}
{"type": "tool_reference", "tool_name": "mcp__pinpoint__room_summary"}
{"type": "tool_reference", "tool_name": "mcp__pinpoint__open_pins"}
{"type": "tool_reference", "tool_name": "mcp__pinpoint__health"}

TOOL CALL: mcp__pinpoint__list_rooms {}

TOOL RESULT:
[
  {
    "id": "r_atrium",
    "title": "Harbour Office Atrium",
    "clientName": "Nordvik Properties",
    "status": "approved",
    "createdAt": "2026-09-21T14:30:00",
    "approvedAt": "2026-09-28T10:00:00",
    "approvedBy": "Jonas Berg",
    "openPinCount": 0
  },
  {
    "id": "r_lakeside",
    "title": "Lakeside Villa — Round 2",
    "clientName": "Marta Lind",
    "status": "open",
    "createdAt": "2026-10-05T09:12:00",
    "approvedAt": null,
    "approvedBy": null,
    "openPinCount": 2
  }
]

TOOL CALL: mcp__pinpoint__room_summary {"room_id": "r_atrium"}

TOOL CALL: mcp__pinpoint__room_summary {"room_id": "r_lakeside"}

TOOL RESULT:
{
  "id": "r_atrium",
  "title": "Harbour Office Atrium",
  "clientName": "Nordvik Properties",
  "status": "approved",
  "images": [
    {
      "id": "i_atrium",
      "title": "Atrium, ground level",
      "superseded": false,
      "pins": {
        "fix": {
          "open": 0,
          "resolved": 1
        },
        "question": {
          "open": 0,
          "resolved": 0
        },
        "like": 1
      }
    }
  ],
  "totals": {
    "fix": {
      "open": 0,
      "resolved": 1
    },
    "question": {
      "open": 0,
      "resolved": 0
    },
    "like": 1
  }
}

TOOL RESULT:
{
  "id": "r_lakeside",
  "title": "Lakeside Villa — Round 2",
  "clientName": "Marta Lind",
  "status": "open",
  "images": [
    {
      "id": "i_facade",
      "title": "Lake facade, golden hour",
      "superseded": false,
      "pins": {
        "fix": {
          "open": 1,
          "resolved": 0
        },
        "question": {
          "open": 1,
          "resolved": 0
        },
        "like": 1
      }
    },
    {
      "id": "i_living",
      "title": "Living room",
      "superseded": false,
      "pins": {
        "fix": {
          "open": 0,
          "resolved": 1
        },
        "question": {
          "open": 0,
          "resolved": 0
        },
        "like": 1
      }
    }
  ],
  "totals": {
    "fix": {
      "open": 1,
      "resolved": 1
    },
    "question": {
      "open": 1,
      "resolved": 0
    },
    "like": 2
  }
}

ASSISTANT:
There are 1 open fix pin across the two demo rooms.

| Room | Open fix pins |
|---|---|
| Harbour Office Atrium (`r_atrium`, approved) | 0 |
| Lakeside Villa — Round 2 (`r_lakeside`, open) | 1 |

- **Atrium:** its only fix pin is already resolved.
- **Lakeside:** the open fix pin is on "Lake facade, golden hour". The Living room's fix pin is resolved.

`list_rooms` reports 2 open pins for Lakeside. That figure includes the open question pin on the facade image, so it overstates the fix count.
```

The counts match the seed: Lakeside Villa — Round 2 has 1 open fix pin,
Harbour Office Atrium has 0. The model called `list_rooms` and then
`room_summary` for each room before answering. Its closing remark is correct and
is the reason `room_summary` exists: `list_rooms` reports `openPinCount` 2 for
Lakeside because that count includes the open question pin.
