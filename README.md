# Pinpoint

Client feedback on architectural visualization renders: a studio opens a review
room, uploads the renders of a round and shares one link; the client drops
numbered pins on the images and says what to change; the studio replies,
resolves and re-uploads.

Final project for the [AI Dev Tools Zoomcamp 2026](https://github.com/DataTalksClub/ai-dev-tools-zoomcamp).

- Specification: [`product-spec.md`](product-spec.md)
- Agent instructions: [`AGENTS.md`](AGENTS.md) · process and roles in [`_docs/`](_docs/)
- How AI tools were used: [`docs/ai-usage-report.md`](docs/ai-usage-report.md)

Status: specification and backlog. Code arrives issue by issue.

## Getting started

- `make sync` — install backend dependencies (`uv sync`)
- `make run` — start the backend with auto-reload
- `make test` — run the backend test suite
- `make frontend-test` — install frontend dependencies and run the frontend
  test suite (also runnable directly via `cd frontend && npm install`)

`make up` and `make down` are not functional yet — they print a pointer to
issue #8 and exit non-zero until the Docker Compose stack exists.

## Running frontend and backend together

For local development against the real backend (no mock), run each half in
its own terminal:

- Copy `.env.example` to `.env` at the repo root first, if you have not
  already — it sets `VITE_API_BASE_URL=http://localhost:8091`, which the
  frontend needs to talk to the real backend instead of its built-in mock.
- Terminal 1: `make run` (backend on `:8091`).
- Terminal 2: `cd frontend && npm install && npm run dev` (frontend on
  Vite's default `:5173`).

This two-terminal recipe is the supported way to run both locally — not a
`make dev` target (see `_docs/decisions.md`/issue #5 for why). `make
up`/`make down` (Docker Compose) are for issue #8 and are unrelated to this
local-dev workflow.
