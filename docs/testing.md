# Testing

Four suites, each exercising a different layer. Run them in this order when
in doubt: backend unit → frontend unit → integration → end-to-end.

## Backend unit

Fast, in-process tests against FastAPI's `TestClient` — no Docker, no
Postgres, nothing else running. Covers the routers and business rules
(ownership, closed-room rejections, reopen-on-reply, upload validation,
export formatting, …) against the in-memory store.

What this layer covers: every business rule the product spec names,
exercised in-process against the `Store` interface rather than a real
database — fast enough to run on every change. Rubric: exercises the
AI-assisted workflow's test-first discipline (criterion 2) and, run
against the Postgres-backed `backend-test` service below, the same
database-agnostic store code the CI/CD pipeline's `backend (postgres)`
job runs (criterion 11).

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

What this layer covers: components, hooks, and pure logic (pin coordinate
math, request shaping in `http.ts`) in isolation, fast enough to run with
no backend at all. Rubric: exercises the AI-assisted workflow's test-first
discipline (criterion 2) — the same discipline that caught the reopen-on-
reply gap during issue #2 and the object-URL leak during issue #7 before
either reached `main`.

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

What this layer covers: real HTTP, over the network, against the real
Postgres-backed Compose stack — the same stack the CI/CD pipeline's
`stack` job brings up, so a pass here is the same signal that job relies
on before `deploy` ever runs. Rubric: directly serves criterion 11
(CI/CD) and, via the restart-persistence test, criterion 14
(reproducibility) — data really does survive a backend restart, not just
in theory.

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

A separate Node/TypeScript project (`e2e/`), using `@playwright/test`,
that drives a real Chromium browser against the real Compose stack — no
mocks, no dev server. It covers the same user-facing flows as
`_docs/test-scenario.md`, but through the browser instead of direct HTTP:
signup, room creation, upload, sharing the guest link, placing and
replying to pins, resolve/reopen, approving the round, and closing the
room.

The suite uses two separate Playwright `BrowserContext`s per test —
studio and guest — so they never share cookies, `localStorage`, or auth,
exactly like a real studio and a real client reviewing from different
browsers. `review-flow.spec.ts` runs the full scenario end to end in one
test; `pin-position.spec.ts` independently checks that a pin's `%`-based
position (`frontend/src/lib/pins/coords.ts`) survives the image being
resized across several viewport sizes. Every "the other side sees this
without reloading" assertion relies on the app's own 3-second polling
(`POLL_MS` in `frontend/src/lib/queries.ts`), not on a push update — there
are no WebSockets in this project (`_docs/decisions.md`) — and no
`page.reload()` calls appear anywhere in the scenario spec.

What this layer covers: a real browser driving the same user-facing
scenario as `_docs/test-scenario.md`, through two isolated contexts, the
closest this project gets to how a studio and a client actually
experience the app. Rubric: also part of the CI/CD pipeline's `stack` job
(criterion 11), and `make e2e`'s own up/none/down symmetry — leaving the
stack exactly as it found it — is itself a reproducibility property
(criterion 14): the same command behaves correctly whether or not a stack
was already running.

```
make e2e
```

`make e2e` installs the Chromium browser binary if it isn't already
present, then checks whether the stack is already reachable at
`/health`. If it's already up (e.g. you already ran `make up`), the
target leaves it running and does nothing further to it. If not, it
starts the stack itself with the same command `make up` runs
(`docker compose up -d --build --wait`), runs the suite, and — only in
that case — tears the stack back down afterward with the same command
`make down` runs (`docker compose down -v`). Either way, `make e2e` exits
with the test run's own exit code and leaves the stack exactly as it
found it.

On failure, a trace and screenshot are kept (only on failure — see
`e2e/playwright.config.ts`) and an HTML report is written under `e2e/`.

See `e2e/README.md` for running the suite directly with
`npx playwright test` (headless, `--headed`, `--debug`), and for opening
the HTML report or a kept trace.
