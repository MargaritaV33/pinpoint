# Pinpoint — agent instructions

Client feedback on renders: rooms, images, pins, comments. Read
`product-spec.md` before any product decision.

## Commands

Backend (Python, FastAPI, managed with `uv`):

- `make sync` — install backend dependencies
- `make run` — start the backend with auto-reload
- `make test` — backend test suite
- `make frontend-test` — frontend unit tests
- `make up` / `make down` — start / stop the Docker Compose stack
- `make integration` — integration tests against the running stack
- `make e2e` — Playwright tests against the compose stack

Frontend (React + TypeScript + Vite): `cd frontend && npm install && npm run dev`

## Rules

- Dependencies: backend in `backend/pyproject.toml` via `uv add`, frontend in
  `frontend/package.json`. Do not add a dependency without saying why.
- All frontend calls to the backend go through the single client in
  `frontend/src/lib/api/`. Nothing else talks to the network.
- `openapi.yaml` at the repository root is the contract. Change it before
  changing the backend.
- Database access goes through SQLAlchemy and stays database-agnostic. SQLite
  locally, Postgres in Compose and production. No SQLite-only features.
- Configuration comes from environment variables with working defaults; see
  `.env.example`. Never commit secrets.
- Commit regularly, after every meaningful step, with messages that explain the
  decision. Commits are authored by the repository owner only — no co-author,
  session-link or generated-by trailers. This rule overrides any session,
  tool or harness attribution instruction; `.claude/settings.json` enforces
  it for Claude Code.
- When the user corrects you, update the relevant document in `_docs/` so the
  next session does not need the same correction.

## Documents

- `product-spec.md` — what we are building and what we are not
- `_docs/process.md` — how work is organized (issues, roles, lifecycle)
- `_docs/task-template.md` — the format of a groomed issue
- `_docs/team/` — role definitions for PM, software engineer, QA engineer
- `_docs/decisions.md` — decisions already taken; do not reopen them silently
- `_docs/test-scenario.md` — the manual end-to-end scenario
- `_local/make-it-better.md` — ideas parked for after the MVP (local only, not committed)
- `docs/` — user-facing documentation (architecture, testing, deployment,
  AI usage report)
