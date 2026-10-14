# Agent extension pack

Discoverable subagent and skill definitions for Claude Code (and the
course's cross-assistant convention), describing this project's own
already-documented process. See `agent-capabilities/README.md` for how
the canonical and working-copy trees stay in sync.

| Capability | Where it lives | How to invoke | What it's for |
|---|---|---|---|
| `pm` subagent | `.agents/agents/pm.md`, `.claude/agents/pm.md` | Launch the `pm` subagent by name | Grooms a GitHub issue per `_docs/team/pm.md` and `_docs/process.md` before anyone implements it |
| `software-engineer` subagent | `.agents/agents/software-engineer.md`, `.claude/agents/software-engineer.md` | Launch the `software-engineer` subagent by name | Implements one already-groomed issue per `_docs/team/software-engineer.md` and `_docs/process.md` |
| `qa-engineer` subagent | `.agents/agents/qa-engineer.md`, `.claude/agents/qa-engineer.md` | Launch the `qa-engineer` subagent by name | Verifies finished work against the issue's acceptance criteria and posts a PASS/FAIL verdict, per `_docs/team/qa-engineer.md` and `_docs/process.md` |
| `on-call-responder` subagent | `.agents/agents/on-call-responder.md`, `.claude/agents/on-call-responder.md` | Launch the `on-call-responder` subagent by name | Diagnoses a production symptom (`/health` shape, failed `deploy` job, Render 5xx) using `docs/deployment.md` and `docs/release-process.md` as its runbook, and proposes — never runs — the fix |
| `implement-issue` skill | `.agents/skills/implement-issue/SKILL.md`, `.claude/skills/implement-issue/SKILL.md` | Invoke the `implement-issue` skill (e.g. `/implement-issue`) | Walks one issue through the PM → Engineer → QA lifecycle from `_docs/process.md`, including the `docs/ai-usage-report.md` log entry each step appends |
| `release` skill | `.agents/skills/release/SKILL.md`, `.claude/skills/release/SKILL.md` | Invoke the `release` skill (e.g. `/release`) | Walks a push to `main` through CI to a verified Render deploy, and names the two rollback paths if `deploy` fails |
| `incident-response` skill | `.agents/skills/incident-response/SKILL.md`, `.claude/skills/incident-response/SKILL.md` | Invoke the `incident-response` skill (e.g. `/incident-response`) | Diagnoses a live production problem, decides rollback vs. fix-forward, and writes the entry to `ops/incidents/` |
| Canonical/working-copy sync | `.agents/agents/`, `.agents/skills/` (canonical) kept aligned with `.claude/agents/`, `.claude/skills/` (working copy) via root `Makefile` and `scripts/check-agents-sync.sh` | Run `make sync-agents`, then `bash scripts/check-agents-sync.sh` | Copies canonical subagent/skill files into the tree Claude Code actually loads, and fails CI's `agents-sync` job if the two trees ever drift apart |
| `MCP server` | `mcp-server/`, `.mcp.json` | The `pinpoint` MCP server in Claude Code (start Claude Code in the repo root and approve it once), or `uv run --directory mcp-server pinpoint-mcp` | Read-only room, pin and approval queries against a running Pinpoint (`health`, `list_rooms`, `room_summary`, `open_pins`, `approve_status`); see `mcp-server/README.md` |

Later issues extend this table as new subagents and skills are added.

## MCP server

`mcp-server/` is a small read-only MCP server (Python, FastMCP, stdio) that lets
an assistant ask a running Pinpoint instance about a studio's rooms. The
repo-root `.mcp.json` registers it as `pinpoint`; configuration, tools, the
read-only guarantee, tests and setup for other assistants are in
`mcp-server/README.md`.

### Live demo transcript

A real, unedited run. Date: 2026-10-14. Repository commit: `8f64914`
(`git rev-parse --short HEAD`, clean working tree). Stack: `make up` (Docker
Compose, seed data). Client: Claude Code 2.1.299, model `claude-sonnet-5-5`, a
fresh headless session started from the repo root so `.mcp.json` was picked up,
with `PINPOINT_EMAIL=demo@pinpoint.studio` and `PINPOINT_PASSWORD=pinpoint` (the
public seed account) in the environment. The exact command, and what the
rendering script drops, are in `mcp-server/README.md`. No token, password or
`guestToken` appeared in the run, so nothing was replaced by `[redacted]`.

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

The model called `list_rooms` and then `room_summary` for each room, and the
counts match the seed: Lakeside Villa — Round 2 has 1 open fix pin, Harbour
Office Atrium has 0.
