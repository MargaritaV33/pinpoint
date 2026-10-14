# Architecture

Grounded in the files that actually implement each piece —
`backend/app/config.py`, `backend/app/store/sqlalchemy/models.py`,
`openapi.yaml`, `docker-compose.yaml`, `render.yaml`, `Dockerfile`, and
`.github/workflows/ci.yml` — not an aspirational diagram. See
`_docs/decisions.md` for the reasoning behind each choice; this document
describes what was decided and built, it does not re-decide anything.

## Topology

Two different topologies exist side by side, and they are genuinely
different — not the same diagram drawn twice. Local development runs the
frontend and backend as two separate processes on two separate ports,
talking cross-origin. Everything else (Docker Compose, Render) runs one
process serving both, same-origin, behind a database that is Postgres
instead of SQLite.

```mermaid
flowchart TB
    subgraph local["Local development — two terminals, cross-origin"]
        direction LR
        Browser1["Browser SPA<br/>(Vite dev server, :5173)"]
        FastAPI1["FastAPI backend<br/>(make run, :8091)"]
        SQLAlchemy1["SQLAlchemy"]
        SQLite["SQLite file<br/>(pinpoint.db)"]
        Browser1 -- "fetch, cross-origin<br/>(CORS_ORIGINS)" --> FastAPI1
        FastAPI1 --> SQLAlchemy1
        SQLAlchemy1 --> SQLite
    end

    subgraph samoorigin["Docker Compose / Render — one image, same-origin"]
        direction LR
        Browser2["Browser SPA<br/>(served by FastAPI)"]
        FastAPI2["FastAPI backend<br/>(:8100 Compose / Render's port)"]
        SQLAlchemy2["SQLAlchemy"]
        Postgres["Postgres<br/>(Compose service / Render managed DB)"]
        Browser2 -- "fetch, same-origin" --> FastAPI2
        FastAPI2 --> SQLAlchemy2
        SQLAlchemy2 --> Postgres
    end

    subgraph cicd["CI/CD — GitHub Actions"]
        direction LR
        GHA["GitHub Actions<br/>(backend + frontend jobs<br/>&rarr; stack job)"]
        Hook["Render deploy hook"]
        RenderSvc["Render web service<br/>+ managed Postgres"]
        GHA -- "on green stack job,<br/>push to main" --> Hook
        Hook --> RenderSvc
    end

    samoorigin -. "same image Render runs" .-> cicd
```

The local-dev topology is real, not a simplification: the Vite dev server
(`:5173`, `strictPort: true` in `frontend/vite.config.ts`) and the FastAPI
backend (`:8091`, `make run`) are two separate origins, so the frontend's
`CORS_ORIGINS` setting matters there and nowhere else. The Compose/Render
topology is same-origin by construction — the Dockerfile's frontend build
stage bakes `VITE_API_BASE_URL=""` into the bundle, so the browser only
ever calls the same origin it was served from, and `CORS_ORIGINS` is inert
there (kept only for parity with the local-dev path; see the root
README's "Environment variables" table).

## Technology choices

| Component | Choice | Why |
|---|---|---|
| Frontend | React + TypeScript + Vite, prototyped in [Lovable](https://lovable.dev) | Course default stack; Lovable produced a working, good-looking demo fast (issue #2) |
| Backend | FastAPI + `uv` + SQLAlchemy, modules split into `routers` / `models` / `store` / `auth` | Course default; the module split keeps business rules in routers and storage mechanics behind the `Store` interface, so swapping stores (issue #6) touched no router code |
| Database | SQLite locally (`sqlite:///./pinpoint.db`), Postgres in Compose and on Render, both via `DATABASE_URL` | Rubric: the same SQLAlchemy code runs unmodified against different environments |
| Containers | One two-stage `Dockerfile` — a Node stage builds the frontend, a Python stage serves the API and the built frontend from the same origin — plus Postgres as a Compose service | Course default; same-origin serving removes an entire class of CORS problems in anything but local dev |
| Deployment | Render Blueprint (`render.yaml`): one web service (free plan) + one managed Postgres (free plan) | Fastest path to a public URL for this attempt; AWS/CloudFormation considered for a second attempt |
| CI/CD | GitHub Actions (`.github/workflows/ci.yml`): backend + frontend test jobs in parallel &rarr; a `stack` job (Compose up, integration, e2e) &rarr; a `deploy` job that calls Render's deploy hook and polls `/health` for the matching commit | Rubric criterion 11 |

## Request flow: studio vs. guest auth

The two call shapes in `openapi.yaml` never mix:

- **Studio calls** carry `Authorization: Bearer <token>`. The token is a
  JWT issued by `POST /auth/signup` or `POST /auth/login`. `openapi.yaml`'s
  `bearerAuth` security scheme describes exactly this: "Studio session
  token, sent as `Authorization: Bearer <token>`. Guest routes never use
  this scheme." Logging out (`POST /auth/logout`) revokes the token
  server-side by deleting its row from the `sessions` table, so a stolen
  but logged-out token stops working immediately rather than just expiring
  on its own clock.
- **Guest calls** carry no `Authorization` header and no bearer token at
  all. Every guest endpoint is shaped `/guest/{guestToken}/...` — the
  room's `guestToken` is a path segment, checked per-request against that
  room's own stored `guest_token` column, not a issued, revocable session.
  The client's display name is never sent to the server as part of
  authentication; it lives only in the browser (`localStorage`), attached
  to each request's body as plain `authorName` fields on pins/comments.

This means a guest token only ever opens its own room (there is nothing
else it could open — it is not a credential, it is the room's own
identifier), and a studio user's bearer token never lets them act on a
room they don't own — the ownership check (`room.owner_id` against the
authenticated user's id) is a router-level business rule, not part of the
auth scheme itself.

## Data model

Five tables carry the product's actual data, defined in
`backend/app/store/sqlalchemy/models.py`. Column types are deliberately
database-agnostic (`String`, `DateTime`, `Float`, `Integer`, `Boolean`,
`LargeBinary`) so the same models run unmodified against SQLite and
Postgres.

```mermaid
erDiagram
    studio_users {
        string id PK
        string email
        string name
        string password_hash
    }
    rooms {
        string id PK
        string owner_id FK
        string title
        string client_name
        datetime created_at
        string status
        string guest_token
        datetime approved_at
        string approved_by
    }
    images {
        string id PK
        string room_id FK
        string title
        string content_type
        bytes data
        bool superseded
        datetime created_at
    }
    pins {
        string id PK
        string image_id FK
        int number
        float x
        float y
        string type
        string status
        datetime created_at
    }
    comments {
        string id PK
        string pin_id FK
        string text
        string author_name
        string author_role
        datetime created_at
    }
    studio_users ||--o{ rooms : "owner_id"
    rooms ||--o{ images : "room_id"
    images ||--o{ pins : "image_id"
    pins ||--o{ comments : "pin_id"
```

- `rooms.owner_id` &rarr; `studio_users.id` (no DB-level FK constraint in
  the model — enforced in router code, since `owner_id` is also the join
  key for "studio's own rooms" queries).
- `images.room_id` &rarr; `rooms.id` (real `ForeignKey("rooms.id")`).
- `pins.image_id` &rarr; `images.id` (real `ForeignKey("images.id")`).
- `comments.pin_id` &rarr; `pins.id` (real `ForeignKey("pins.id")`).

A sixth table, `sessions` (`token` primary key, `user_id`), exists purely
as an auth implementation detail — it backs `create_session` /
`get_session_user_id` / `delete_session` so logout can revoke a token
server-side (see "Request flow" above). It is not part of the product
data model above and carries no foreign key to `studio_users`.

## Environment matrix

| Environment | `DATABASE_URL` | How it's actually set | Driver normalization |
|---|---|---|---|
| Local (`make run`, no Docker) | `sqlite:///./pinpoint.db` | `.env.example`'s default, loaded via `.env` if present, otherwise `Settings`'s own field default in `backend/app/config.py` | Not needed — a `sqlite:///` URL passes through `Settings._normalize_database_url` unchanged |
| Docker Compose (`make up`) | `postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}` | Rebuilt in `docker-compose.yaml`'s `app.environment.DATABASE_URL` from the `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` vars plus the `postgres` service's own Compose-network hostname — the root `.env`'s SQLite default is deliberately never read here | Already in `postgresql+psycopg://` form at the Compose-file level, so the normalizer is a no-op in this path |
| Render (production) | Render's managed-Postgres `connectionString`, wired via `render.yaml`'s `fromDatabase: { name: pinpoint-db, property: connectionString }` | Set automatically by the Blueprint when it's applied — no human types a value in | Render's connection string is a bare `postgres://` or `postgresql://` URL (SQLAlchemy's default driver resolution for that scheme is `psycopg2`, which this backend doesn't install — only `psycopg[binary]`); `Settings._normalize_database_url`, a Pydantic `field_validator` on the `database_url` field, rewrites it to `postgresql+psycopg://` so every reader of `settings.database_url` — the SQLAlchemy engine included — gets the corrected URL with no Render-specific command-line rewriting (see issue #12's incident and `backend/app/config.py`) |

The normalization lives in exactly one place (`Settings._normalize_database_url`)
so every consumer gets it for free, regardless of which environment set the
raw value.
