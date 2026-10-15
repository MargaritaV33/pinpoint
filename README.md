# Pinpoint

[![CI](https://github.com/MargaritaV33/pinpoint/actions/workflows/ci.yml/badge.svg)](https://github.com/MargaritaV33/pinpoint/actions/workflows/ci.yml)

Archviz studios collect client feedback on renders over email, WhatsApp, and
screenshots with a red circle drawn on top — comments aren't anchored to the
image, nobody can tell which ones are done, and the history is gone by the
next round. Pinpoint gives the client a guest link to drop numbered `fix` /
`question` / `like` pins directly on each render, and gives the studio back a
threaded, resolvable, exportable list per room.

The scope is deliberately small: Pinpoint exists to demonstrate the course's
AI-assisted workflow end to end — spec → backlog → PM/Engineer/QA agents →
contract-first `openapi.yaml` → tests at every layer → containers → CI/CD →
deploy — not to compete with Figma or ship a feature-complete product. See
`_docs/decisions.md`'s "Scope statement" row. Rubric criteria 12 (agent
extension pack) and 13 (security, audit and operations) were added in a second
phase.

Final project for the [AI Dev Tools Zoomcamp 2026](https://github.com/DataTalksClub/ai-dev-tools-zoomcamp).

## Live demo

**<https://pinpoint-muou.onrender.com>**

Log in as the seeded demo studio:

- Email: `demo@pinpoint.studio`
- Password: `pinpoint`

The web service is on Render's free plan and spins down after a period of
inactivity, so the first request after idling has to wake it back up. We
measured about 33 seconds (4 of 5 attempts, 15 Oct 2026; see
[`ops/diagnosis-2026-10-15-cold-start.md`](ops/diagnosis-2026-10-15-cold-start.md));
Render's documentation says about one minute. See also `docs/deployment.md`'s
"Free plan limits". Subsequent requests are fast.

The free database expires about 13 Nov 2026 (see the dated reminder in
[`ops/runbook.md`](ops/runbook.md#reminder-free-database-expires-about-13-nov-2026)).

## Quick start

Commands below assume a POSIX-style shell (bash, Git Bash, or WSL on
Windows) — `&&` chaining doesn't work the same way in Windows PowerShell.
On Windows, run these in Git Bash, not PowerShell or cmd.exe.

### Clone the repository

```sh
git clone https://github.com/MargaritaV33/pinpoint.git
cd pinpoint
```

### Prerequisites

- `git`
- [`uv`](https://docs.astral.sh/uv/) (backend package/venv manager). If it's
  not already installed: `pip install uv`, or the installers linked from
  that page. After installing via `pip`, make sure the directory `uv` lands
  in is actually on your `PATH` (e.g. `pip show -f uv` to find it) — a
  successful `pip install uv` does not guarantee `uv --version` works yet.
  In Git Bash, `pip show -f uv` prints a `Location:` (a `...\site-packages`
  folder) and `..\Scripts\uv.exe`; add the `Scripts` folder beside that
  `site-packages` as a Git Bash path (it differs per machine):
  `export PATH="/c/Users/<you>/AppData/Roaming/Python/Python3xx/Scripts:$PATH"`,
  and put that line in `~/.bashrc` to keep it. `python -m uv` runs the same tool
  without touching `PATH` (e.g. `python -m uv --version`), but the `make`
  targets call plain `uv`, so they still need the `PATH` fix.
- Node.js 20+ (CI itself runs Node 22; 20 is the floor)
- Docker with Compose v2 (`docker compose`, not the standalone
  `docker-compose`) — Docker Desktop (or your daemon) needs to actually be
  running, not just installed.
- GNU Make. Not installed by default on Windows — every command below is a
  `make` target; install it via Git Bash (bundled with Git for Windows),
  WSL, Chocolatey (`choco install make`), or Scoop (`scoop install make`).
- Ports `8091`, `5173`, and `8100` free on your machine — the backend,
  frontend dev server, and Docker Compose stack each bind one of these and
  fail with "port already in use" if something else is already listening.
- Network access — installing dependencies, building the Docker image, and
  `make e2e`'s first run (which downloads the Chromium browser binary) all
  need to reach the internet.

### Run the backend

```sh
make sync   # cd backend && uv sync
make run    # cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8091
```

Serves on `:8091` against SQLite by default
(`DATABASE_URL=sqlite:///./pinpoint.db`) — no Docker, no Postgres needed.
`make run` keeps the terminal until you stop it with Ctrl+C, so open a second
terminal for the next steps (`curl`, the frontend).
There's no route at `/` (API-only, `404` is expected); check it's up with
`curl http://localhost:8091/health` instead. A one-time
`WatchFiles detected changes in '.venv\...'. Reloading...` line on first
start is harmless — `--reload` is watching the freshly-created virtualenv
too; it settles after that.

### Run the frontend against the real backend

Copy `.env.example` to `.env` at the repo root first:

```sh
cp .env.example .env
```

This sets `VITE_API_BASE_URL=http://localhost:8091`, which the frontend
needs to talk to the real backend instead of its built-in mock. Then, with
the backend from the previous step already running:

```sh
cd frontend && npm install && npm run dev
```

Vite serves the frontend on `:5173` (pinned via `strictPort: true` in
`frontend/vite.config.ts`). This two-terminal recipe — backend in one
terminal, frontend in the other — is the supported way to run both locally;
there is no `make dev` target (see `_docs/decisions.md` / issue #5 for why).

**If you plan to run `make up` later in this session**, restore the
committed lockfile first: `git checkout -- frontend/package-lock.json`. On
non-Linux platforms, `npm install` rewrites `frontend/package-lock.json`,
dropping Linux-only optional dependencies the Docker build's `npm ci` step
needs byte-for-byte — if you skip this, `make up`'s image build fails with
`npm error Missing: @emnapi/core@... from lock file`. See
`docs/testing.md` for the full explanation.

### Run tests

```sh
make test            # backend: pytest, in-process against FastAPI's TestClient
make frontend-test    # frontend: vitest, against the mock API client
```

`make frontend-test` also runs `npm install`, so it has the same
lockfile-rewriting effect described above — run
`git checkout -- frontend/package-lock.json` afterward if you're about to
run `make up` or `make e2e` (`make e2e` builds its own stack when none is
running, and that build fails at `npm ci` on a rewritten lockfile).

### Run the full stack

If you ran `npm install` in `frontend/` earlier in this session (the
previous two sections both do), restore the committed lockfile first —
otherwise this step's image build fails:

```sh
git checkout -- frontend/package-lock.json
```

```sh
make up    # docker compose up -d --build --wait
```

One two-stage image (Node builds the frontend, Python/FastAPI serves the API
and the built frontend from the same origin — no CORS needed), Postgres as a
second Compose service, no manual steps. Once both services report healthy,
the app is reachable at `http://localhost:${APP_PORT:-8100}` (default
`http://localhost:8100`) — the first request creates the database tables and
loads the demo seed data automatically.

```sh
make down  # docker compose down -v
```

Stops the stack and removes its Postgres volume, so the next `make up`
starts from a clean, freshly-seeded database.

### Integration and end-to-end

```sh
make up            # bring the stack up first — integration doesn't start it
make integration   # real HTTP against the running stack
make e2e           # Playwright against a real browser; brings its own stack up/down if none is running
```

Restore `frontend/package-lock.json` first (`git checkout -- frontend/package-lock.json`)
if `npm install` or `make frontend-test` ran earlier: `make e2e` builds the same
image as `make up`, and with no stack running it fails at `npm ci` otherwise.

See `docs/testing.md` for what each suite actually covers and how they
differ.

### Deploy

See `docs/deployment.md` (Render Blueprint, environment variables, rollback)
and `docs/release-process.md` (what triggers a CI-gated deploy, the smoke
test, rollback). When production looks wrong, start at
[`ops/runbook.md`](ops/runbook.md) (health check, logs, "is it our app, Render or
the database?" decision tree); past incidents are in `ops/incidents/`.

## Running with Docker Compose

`make up` brings up one Postgres-backed Pinpoint from a single two-stage
image (Node builds the frontend, Python/FastAPI serves the API and the
built frontend from the same origin — no CORS needed), with no manual steps.

**`docker build` alone (no Compose) is not a documented, supported way to
run the app.** The app needs Postgres, per `_docs/decisions.md`'s "one
two-stage image + Postgres in Compose" row; this project deliberately does
not offer an all-in-one single-container-with-embedded-Postgres
alternative. `docker build -t pinpoint .` is mentioned below only as "how
the image that Compose runs is built," not as another way to run Pinpoint —
running the bare image directly (`docker run`) would boot against
`DATABASE_URL`'s default, `sqlite:///./pinpoint.db`, inside the container's
own ephemeral filesystem, which is not supported.

To build just the image Compose uses (no `.env`/build-arg needed — it
defaults to the same-origin `VITE_API_BASE_URL=""`):

```sh
docker build -t pinpoint .
```

### Verifying the Postgres path

`docker compose up`'s `app`/`postgres` services never expose Postgres to
the host. To run the backend test suite for real against the stack's own
Postgres instead of local SQLite, use the `backend-test` service (under
`profiles: ["test"]`, so a plain `make up`/`docker compose up` never starts
it):

```sh
docker compose up -d --wait postgres
docker compose --profile test run --rm backend-test
```

Exit code `0` and pytest's own summary line are the pass/fail signal.

## Environment variables

All variables live in root `.env.example`; copy it to `.env` to override
any default. Docker Compose loads `.env` automatically (no `env_file:`
block); the last column states exactly what `docker compose up` does with
each one.

| Variable | What it does | Default | Under Docker Compose |
|---|---|---|---|
| `DATABASE_URL` | Backend database connection string | `sqlite:///./pinpoint.db` | Ignored — `app`'s `DATABASE_URL` is always rebuilt from `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` + the `postgres` service hostname, so Compose never runs on SQLite |
| `JWT_SECRET` | Signs session tokens | `local-development-secret-change-me` | Passed straight through |
| `ACCESS_TOKEN_MINUTES` | Session token lifetime | `60` | Passed straight through |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:5173,http://localhost:8091` | Passed straight through (irrelevant for same-origin requests inside the container; kept for parity with the non-Docker path) |
| `MAX_UPLOAD_MB` | Max render upload size | `15` | Passed straight through |
| `ENVIRONMENT` | Free-form environment label | `development` | Passed straight through |
| `VITE_API_BASE_URL` | Frontend's backend base URL, inlined at `npm run build` time | `http://localhost:8091` (for the two-terminal local-dev recipe above) | Ignored — `app`'s build always hardcodes the literal `""` (same-origin), regardless of this file |
| `APP_PORT` | Host port the `app` service publishes | `8100` | Consumed by `docker-compose.yaml` only; irrelevant outside Compose |
| `POSTGRES_USER` | Postgres username | `pinpoint` | Consumed by `docker-compose.yaml` only |
| `POSTGRES_PASSWORD` | Postgres password | `pinpoint` | Consumed by `docker-compose.yaml` only |
| `POSTGRES_DB` | Postgres database name | `pinpoint` | Consumed by `docker-compose.yaml` only |

## How this was built with AI

Pinpoint was built with Claude Code running fresh-session PM / Software
Engineer / QA Engineer role agents per `_docs/process.md`'s lifecycle, with
the frontend prototyped in Lovable. Start here:

- Specification: [`product-spec.md`](product-spec.md)
- Process and roles: [`_docs/process.md`](_docs/process.md) ·
  [`_docs/team/`](_docs/team/) (PM, Software Engineer, QA Engineer role
  definitions)
- Decisions already taken: [`_docs/decisions.md`](_docs/decisions.md)
- Agent instructions: [`AGENTS.md`](AGENTS.md)
- Full running log, tools used, what went wrong and was caught:
  [`docs/ai-usage-report.md`](docs/ai-usage-report.md)
- Security scans, code-review audit, agent-extension risks and the AI tool and
  data policy: [`security/`](security/)

## Agent extension pack

Skills, subagents, an MCP server and hooks for Claude Code; the full table is
[`docs/agent-extension-pack.md`](docs/agent-extension-pack.md). Start `claude` in the repo root, then:
- Skill: `/implement-issue how does an issue move from open to PASS? Explain only, change nothing.`
  (`implement-issue` walks one issue through PM, Engineer and QA). Headless: `claude -p "/implement-issue ..." --allowedTools "Read,Grep,Glob"`.
- Subagent: `use the on-call-responder subagent to say what /health should return`
  (read-only: its tools are Read, Grep, Glob and WebFetch). Headless, we ran it with `Agent` added to `--allowedTools`: harmless, and some Claude Code versions or settings may need it to launch a subagent.
- MCP server (read-only questions about a running Pinpoint), two commands:

```sh
make up
PINPOINT_EMAIL=demo@pinpoint.studio PINPOINT_PASSWORD=pinpoint claude   # in the repo root
```

Claude Code asks once to approve the project's `pinpoint` server, which `.mcp.json`
runs as `uv run --directory mcp-server pinpoint-mcp`: plain `uv`, so the `PATH` fix above must be active in the shell that launches `claude`. Then ask "how many open fix
pins are in each demo room?" (details: [`mcp-server/README.md`](mcp-server/README.md)).
Tests: `make hooks-test` (the hooks in `agent-hooks/`), `make mcp-test` (the MCP server, HTTP mocked), `make mcp-integration` (needs `make up`; the MCP integration tests against the live stack).

## Security and operations

- Security, in [`security/`](security/): [`semgrep-report.md`](security/semgrep-report.md), [`dependency-audit.md`](security/dependency-audit.md),
  [`pr-audit.md`](security/pr-audit.md), [`agent-extension-security.md`](security/agent-extension-security.md), [`ai-tool-and-data-policy.md`](security/ai-tool-and-data-policy.md).
- Operations: [`ops/runbook.md`](ops/runbook.md), [`ops/incidents/`](ops/incidents/README.md), [`ops/observability.md`](ops/observability.md),
  [`ops/diagnosis-2026-10-15-cold-start.md`](ops/diagnosis-2026-10-15-cold-start.md).
- Semgrep scan: needs Docker and a clean `git archive` export of the tracked files, never a working tree holding `.env` or `_local/`. Commands:
  "How to reproduce" in [`security/semgrep-report.md`](security/semgrep-report.md#how-to-reproduce); documented result: 19 findings, none from `p/secrets`.

## Repository map

- `backend/` — FastAPI + SQLAlchemy backend (routers / models / store / auth)
- `frontend/` — React + TypeScript + Vite frontend, single API client in
  `src/lib/api/`
- `e2e/` — Playwright end-to-end tests against a real browser and a real
  Compose stack
- `integration/` — HTTP integration tests against a running Compose stack,
  its own `uv` project
- `mcp-server/` — read-only MCP server so an AI assistant can query a running
  Pinpoint; see [`mcp-server/README.md`](mcp-server/README.md)
- `.mcp.json` — registers the MCP server as `pinpoint` for Claude Code
- `.agents/` — canonical subagent and skill definitions (`agents/`, `skills/`)
- `.claude/` — the real-file working copy Claude Code loads (`agents/`,
  `skills/`, generated by `make sync-agents`) and `settings.json`, which wires
  the hooks
- `agent-capabilities/` — how `.agents/` and `.claude/` stay in sync
- `agent-hooks/` — Claude Code hooks (guardrails) and their tests
- `custom-agent/` — reference for the `on-call-responder` subagent
- `scripts/` — `check-agents-sync.sh`, run by the CI job `agents-sync`
- `security/` — Semgrep report, dependency audit, PR audit, agent-extension
  security, AI tool and data policy
- `_docs/` — process, team role definitions, decisions already taken
- `docs/` — this set of user-facing docs: architecture, testing, deployment,
  release process, AI usage report
- `openapi.yaml` — the API contract; change it before changing the backend
- `ops/` — operations: [`runbook.md`](ops/runbook.md), blameless
  [`incidents/`](ops/incidents/README.md), [`observability.md`](ops/observability.md)
- `.github/workflows/ci.yml` — the CI pipeline and the Render deploy job
- `render.yaml` — the Render Blueprint (web service + managed Postgres)
- `docker-compose.yaml` — the local Postgres-backed stack
- `Dockerfile` — the one two-stage image Compose and Render both run

Root files the map leaves out: `README.md` (this file), `AGENTS.md`,
`CLAUDE.md`, `product-spec.md`, `Makefile`, `.env.example`, `.gitignore`,
`.gitattributes`, `.dockerignore`, `.semgrepignore`.
