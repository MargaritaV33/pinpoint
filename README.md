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
