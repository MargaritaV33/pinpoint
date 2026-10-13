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
up`/`make down` (Docker Compose, below) are unrelated to this local-dev
workflow: SQLite stays the default for this path (`backend/app/config.py`'s
`DATABASE_URL` default and `backend/app/store/sqlalchemy/engine.py` are
unchanged), and `make run`/`make test` never need Docker or Postgres.

## Running with Docker Compose

`make up` brings up one Postgres-backed Pinpoint from a single two-stage
image (Node builds the frontend, Python/FastAPI serves the API and the
built frontend from the same origin — no CORS needed), with no manual steps:

```sh
make up    # docker compose up -d --build --wait
```

Once both services report healthy, the app is reachable at
`http://localhost:${APP_PORT:-8100}` (default `http://localhost:8100`) —
the first request creates the database tables and loads the demo seed data
automatically (`SQLAlchemyStore.__init__`: `Base.metadata.create_all`, then
`_seed()` only if empty — no extra step here).

```sh
make down  # docker compose down -v
```

Stops the stack and removes its Postgres volume, so the next `make up`
starts from a clean, freshly-seeded database.

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
