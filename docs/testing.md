# Testing

Four suites, each exercising a different layer. Run them in this order when
in doubt: backend unit → frontend unit → integration → end-to-end.

## Backend unit

Fast, in-process tests against FastAPI's `TestClient` — no Docker, no
Postgres, nothing else running. Covers the routers and business rules
(ownership, closed-room rejections, reopen-on-reply, upload validation,
export formatting, …) against the in-memory store.

```
make test
```

The same suite also runs against the real Postgres store, inside the
Compose network, via the `backend-test` service (already how issue #8
verifies the Postgres-backed `SQLAlchemyStore`; not a separate suite of
tests, the same `backend/tests/` run with `TEST_DATABASE_URL` pointed at
Postgres instead of SQLite):

```
docker compose up -d --wait postgres
docker compose --profile test run --rm backend-test
```

## Frontend unit

Vitest. No backend running — the suite exercises components and hooks
against the mock API client (`frontend/src/lib/api/mock.ts`).

```
make frontend-test
```

Caution: this target's `npm install` step (not `npm ci`) re-resolves
`frontend/package-lock.json` against whatever platform it runs on. Running
it on a non-linux/amd64 machine (e.g. Windows, during local development)
can silently rewrite away the linux-only optional entries
(`@emnapi/core`/`@emnapi/runtime`) that issue #9 regenerated so the
Dockerfile's `npm ci` passes — observed directly while verifying that
issue. If `git status` shows `frontend/package-lock.json` changed after
running this target, check the diff before committing; if it dropped those
entries, restore the committed version (`git checkout --
frontend/package-lock.json`) rather than committing the rewrite.

## Integration

A separate `uv` project (`integration/`) that drives an **already-running**
Compose stack over real HTTP with `httpx`, covering auth, room lifecycle
(including `openPinCount`), guest access and permission boundaries, upload
validation and byte-serving, pin threads (resolve/reopen), approve, export,
and — in its own file, run last — persistence across a real
`docker compose restart app`.

It never starts the stack itself. Bring it up first:

```
make up
make integration
```

The base URL defaults to `http://localhost:8100` (matching
`docker-compose.yaml`'s `APP_PORT:-8100`) and is configurable via
`PINPOINT_BASE_URL` for a stack running elsewhere. If the stack isn't up,
`make integration` fails within a few seconds with a readable
connection-refused error (the `httpx` client's 5-second timeout) rather
than hanging.

## End-to-end

**Not built yet — coming in a follow-up issue (#10).** Playwright tests
against the Compose stack, covering the same user-facing flows as
`_docs/test-scenario.md` but through a real browser instead of direct
HTTP. `make e2e` is reserved for this; it does not exist yet.
