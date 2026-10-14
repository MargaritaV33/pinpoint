# AI usage report

Running log of how AI tools were used to build Pinpoint. One entry per step:
what was asked, what came back, what was reviewed or rejected, how it was
verified. Consolidated into a narrative before submission.

## Summary

Pinpoint was built almost entirely with **Claude Code**, run as an
orchestrator spawning fresh-session **PM**, **Software Engineer**, and
**QA Engineer** role agents for nearly every issue, following the lifecycle
in `_docs/process.md` and the role definitions in `_docs/team/`. The one
deliberate exception is the frontend: it was first prototyped in
**Lovable** (issue #2, imported from a private `render-review` repo) to get
a good-looking, working UI fast, then adapted to this repo's conventions
(npm tooling, a single API client in `src/lib/api/`, the `VITE_API_BASE_URL`
env var) rather than built from scratch.

**What worked.** The PM/Engineer/QA split, with a fresh session per role and
per step, meant no single session's self-report was ever trusted as the
final word — QA re-verified everything independently, often by re-running
the engineer's own commands from scratch, diffing against the real
repository state, or reproducing a fix in a scratch copy to confirm it
would actually catch a regression. This caught real problems before they
reached `main`, not just stylistic nits:

- **Issue #4** (backend from the contract): QA cross-checked every
  auth/ownership/business-rule claim with its own live curls rather than
  trusting the engineer's report, and confirmed a real gap in
  `openapi.yaml` itself (`approveRound` missing a documented 404).
- **Issue #6** (SQLAlchemy persistence): QA didn't just read the
  restart-persistence fix, it reproduced the full restart proof itself
  (create data, kill every process on the port, restart, confirm no
  duplicates/no crash) and `sha256sum`-verified the replacement seed images
  were byte-for-byte identical, not just same-named.
- **Issue #8** (Dockerfile/Compose): QA reverted the engineer's
  parent-then-child seeding fix and reran the Postgres suite to confirm the
  `ForeignKeyViolation` bug it fixed was genuinely real, and separately
  reproduced the disclosed `npm ci` lockfile gap in a scratch build before
  accepting the `npm install` deviation.
- **Issue #9** (integration tests): QA independently reproduced the
  `frontend/package-lock.json` reversion risk the engineer had flagged
  (confirmed `npm install` really does strip the Linux-only optional
  entries again), and used `docker inspect` container-start timestamps to
  prove the persistence test's restart was genuinely real, not a no-op.
- **Issue #10** (Playwright e2e): QA ran the full suite three times to rule
  out flakiness, verified both directions of the `make e2e` start/teardown
  symmetry itself, and deliberately broke a different assertion than the
  engineer had to confirm the trace/report mechanism generalizes.
- **Issue #13** (continuous deployment): QA extended the engineer's
  mocked-`curl`/`jq` poll-loop harness with three failure modes the
  engineer hadn't tried (non-JSON body, connection failure, HTTP 500), and
  settled an open question about `autoDeployTrigger`'s type by fetching
  Render's own Blueprint JSON schema rather than reasoning about it.

**What went wrong and was caught.** Three incidents stand out as genuine
bugs, caught before or shortly after they mattered:

- **The issue #12 Render deploy incident.** The first deploy attempt's
  `render.yaml` used a `dockerCommand` override to rewrite `DATABASE_URL`'s
  scheme inline. It was verified locally by simulating the command string
  in isolation (a `subprocess`/`shlex` test) — and still crashed in
  production on the very first real deploy, with
  `sh: 1: DATABASE_URL="postgresql://...@dpg-.../pinpoint_xxuj" uv run
  uvicorn ...: not found` (exit code 127). The fix removed the
  `dockerCommand` override entirely and moved the `postgres://` /
  `postgresql://` → `postgresql+psycopg://` normalization into a
  `Settings` field validator in `backend/app/config.py`, verified this
  time with a real `docker build` + `docker run` against live Postgres —
  not simulated.
- **The issue #7 image-caching/object-URL-leak bug.** `useImageSrc.ts`'s
  authenticated-fetch-to-object-URL pattern was discarding, instead of
  revoking, an object URL from an in-flight fetch that resolved after its
  effect had already been cancelled (e.g. rapid image switching) — a real
  memory leak. A separate stale-cache issue was fixed in the same pass
  with `cache: "no-cache"` (deliberately not `"no-store"`). QA reverted the
  leak fix in a scratch copy and reran the new test suite to confirm it
  would genuinely catch the regression before accepting the coverage as
  real.
- **The issue #5 env-loading and CORS-port findings.** While wiring the
  frontend to the real backend, two separate bugs surfaced in sequence, not
  one. First, Vite's default `envDir` (the `frontend/` project root) never
  read the repo-root `.env`, so `VITE_API_BASE_URL` was never injected and
  `index.ts` silently fell back to `MockApiClient` — found and fixed first,
  by adding `envDir: "../"` to `vite.config.ts`. Only once that fix was in
  place, and `HttpApiClient` was confirmed as the client actually selected
  (the mock was no longer in the picture at all), did a second, unrelated
  bug turn up: the frontend dev server's real default port was 8080 (from
  the Lovable config wrapper), not Vite's assumed 5173, and
  `CORS_ORIGINS`'s default didn't cover it — so a real browser on the real
  origin was loudly CORS-blocked (`400 Disallowed CORS origin`) calling the
  backend, which is the opposite failure mode from silently using the mock.
  QA's first pass correctly failed the issue on this second gap rather than
  treating the wrong port number as a documentation nitpick; the fix
  pinned the dev server to `5173` with `strictPort: true` so it fails
  loudly on conflict instead of silently drifting.

**What I would do differently.** The issue #12 incident is the clearest
recorded lesson: a local simulation of a deploy command — even a faithful
one, with real `subprocess` calls against the real command string — is not
the same as running the real artifact (the built Docker image) under the
real target platform's own invocation semantics. The bug lived entirely in
that gap, and no amount of correctly reasoning about the command string in
isolation would have caught it; only actually building and running the
image, the way issue #12's reopening fix and issue #17 both later did,
surfaces that class of failure. Given the chance to do it again, I would
insist on a real build-and-run verification against the actual deployment
artifact before calling any infra-facing issue done, rather than accepting
an isolated command-string simulation as sufficient evidence — the same
standard the project settled on only after being burned once.

## Appendix: per-issue log

## 2026-10-12 — Spec and bootstrap

- **Tool:** Claude (chat) as brainstorming partner, one question at a time.
- **Input:** vague idea "client feedback on renders"; seven scoping questions
  (users, room, pin, rounds, updates, upload, studio extras).
- **Output:** `product-spec.md`, `_docs/decisions.md`, `_docs/make-it-better.md`,
  `_docs/tasks.md`, `AGENTS.md`, `_docs/process.md`, team role files.
- **Review:** every decision taken by the owner; Options Room and versioning
  explicitly cut; realtime replaced by polling.
- **Verification:** n/a (no code yet). Backlog reviewed before moving to GitHub
  issues.

## 2026-10-12 — Issue #1: Repository skeleton with a passing test

- **Tool:** Claude Code, orchestrator + three subagents (PM, Engineer, QA),
  each a fresh session per `_docs/process.md`.
- **PM input/output:** groomed issue #1 from the one-line backlog entry into
  the `_docs/task-template.md` format — locked backend module layout
  (`routers`/`models`/`store`/`auth`) and the frontend's single API client
  convention (`src/lib/api/`) early so later issues don't rename anything;
  moved real endpoints, product UI, env wiring, Compose, CI and deploy out of
  scope to the issues that own them.
- **Engineer input/output:** implemented the groomed criteria — FastAPI
  `/health` behind a router, one TestClient test; Vite+React+TS scaffold with
  a placeholder `App.tsx` and a no-op API client stub, one Vitest test; root
  `Makefile` (`sync run test frontend-test up down`, with `up`/`down`
  pointing at issue #8); README "Getting started" section. Pinned `vitest` to
  5.0.3 instead of create-vite's default 3.x after `npm audit` flagged a
  critical `tinypool` vulnerability in the default.
- **Review:** QA re-ran every criterion independently (not trusting the
  engineer's comment) — backend/frontend module layout, `/health` response,
  exactly-one-test on each side, `make sync|run|test|frontend-test|up|down`
  behavior, `.gitignore`/`.env.example` untouched, README diff additive, no
  product code or `openapi.yaml` introduced.
- **Verification:** `make sync` (uv sync, exit 0); `make test` (1 passed);
  `make frontend-test` (1 passed, 0 vulnerabilities); `make run` + manual
  `curl /health` → 200 `{"status":"ok"}`; `make up`/`make down` → exit
  non-zero with the issue #8 pointer. QA verdict: PASS on all 16 acceptance
  criteria, posted as a GitHub comment. Orchestrator closed issue #1 and
  pushed `f7ec19a`, `0363311`, `758cb88` to `main`.

## 2026-10-12 — Issue #2: Frontend prototype with a mocked service layer

- **Tool:** Claude Code, orchestrator + three subagents (PM, Engineer, QA),
  each a fresh session per `_docs/process.md`.
- **PM input/output:** reframed the one-line backlog item as an
  import-and-adapt task (the prototype was already built in Lovable in the
  private `render-review` repo) rather than a from-scratch build. Groomed
  checkable criteria for: importing without carrying over `render-review`'s
  git history, npm-only tooling, Lovable-artefact removal without breaking
  the app, no stray backend/analytics code, folding `render-review`'s own
  AGENTS.md into `frontend/README.md`, protecting the `src/lib/api/` shape
  for issue #3, and manual verification against `_docs/test-scenario.md`
  steps 1–7. Caught a real mismatch between the task notes' `VITE_API_URL`
  and root `.env.example`'s `VITE_API_BASE_URL` and made reconciling it a
  criterion.
- **Engineer input/output:** cloned `render-review` (`main`) and replaced the
  issue #1 placeholder with its working tree, no `.git` carried over.
  Converted bun → npm with a committed `package-lock.json`. Removed Lovable
  error-reporting telemetry while keeping generic error-page resiliency
  code. Reconciled the env var to `VITE_API_BASE_URL`. Fixed the Vite config
  so `npm run build` emits a genuine static SPA shell instead of a
  Cloudflare Worker bundle (the Lovable config defaulted to that nitro
  preset). Replaced `frontend/README.md` with run/test/build docs, the
  mock/http switch, demo login, and guest links. Flagged, but did not fix,
  a real gap surfaced by the import: guest replies don't reopen a resolved
  pin (product-spec client story 18) — left for whoever grooms #3.
- **Review:** QA independently re-cloned `render-review` and diffed
  `src/lib/api/` against the imported copy to confirm no signature/type
  changes beyond the documented env-var rename; re-ran the dev server,
  build, and test suite itself rather than trusting the engineer's report;
  checked the exact wording of the step-5 criterion to confirm the
  reopen-by-reply gap was correctly scoped out, not silently ignored.
- **Verification:** `make frontend-test` (26 tests, 4 files, all passing,
  exit 0 — run independently by both engineer and QA); `npx tsc --noEmit`
  clean; `npm run build` → static `.output/public/_shell.html`; `npm run
  dev` + curl on `/`, `/login`, `/g/lakeside-demo`, `/g/atrium-demo` → 200
  with correct content. Test-scenario steps 1–7 verified by a mix of running
  the dev server and reading the corresponding code paths (no browser
  automation available in-session); step 8 correctly skipped (no backend
  yet). QA verdict: PASS on all 18 acceptance criteria. Orchestrator closed
  issue #2 and pushed the seven import/cleanup commits to `main`.

## 2026-10-12 — Issue #3: OpenAPI contract

- **Tool:** Claude Code, orchestrator + three subagents (PM, Engineer, QA),
  each a fresh session per `_docs/process.md`.
- **PM input/output:** derived the contract's scope directly from
  `frontend/src/lib/api/{client.ts,types.ts,validation.ts,mock.ts,http.ts}`
  rather than the one-line backlog description. Verified the original
  issue text's claim that `client.ts` had a `signup` method was wrong (it
  didn't — `login`/`logout`/`getCurrentUser` only) and made adding it an
  acceptance criterion. Locked in conventions already implicit in the code
  (bearer header for studio, `guestToken` as a path segment for guest
  routes) rather than inventing new ones. Corrected a second misconception
  in the original text: there are no separate list-images/list-pins
  endpoints — both are embedded in `RoomDetail` — and explicitly forbade
  adding them. Required `npx @redocly/cli lint` as a mechanical,
  QA-checkable pass/fail gate instead of a visual YAML read.
- **Engineer input/output:** wrote `openapi.yaml` (19 operations, OpenAPI
  3.0.3) covering studio auth (incl. new `signup`), rooms, images (multipart
  upload with 413/415, byte-serving with ETag/Cache-Control), pins/comments,
  guest access, and the `text/plain` export. Added `signup(email, password)`
  to `client.ts`/`mock.ts`/`http.ts` with 400/409 handling. Fixed the
  reopen-on-reply gap flagged during issue #2: `mock.ts`'s
  `addGuestComment` now reopens a resolved `fix`/`question` pin after a
  guest's reply (`addStudioComment` deliberately left unaffected), and the
  rule is spelled out in words in the `openapi.yaml` endpoint description,
  not left as a silent side effect. Added matching test cases.
- **Review:** QA read all ~1000 lines of `openapi.yaml` against every
  acceptance-criteria section rather than sampling, confirmed the reopen
  rule's wording actually appears in the endpoint description (not just
  implied), spot-checked `http.ts` against the contract for drift, and
  diffed the full changeset to confirm no file outside the issue's allowed
  list was touched.
- **Verification:** `npx @redocly/cli lint openapi.yaml` → 0 errors (1
  harmless missing-license-URL warning, run independently by both engineer
  and QA); `make frontend-test` → 4 files, 31 tests passing (up from 26,
  confirmed by QA's own fresh run); `npx tsc --noEmit` in `frontend/` →
  clean. QA verdict: PASS on all 9 acceptance-criteria sections. Orchestrator
  closed issue #3 and pushed `16b9cdb`, `5ccfd39` to `main`.

## 2026-10-12 — Issue #4: Backend from the contract with an in-memory store

- **Tool:** Claude Code, orchestrator + three subagents (PM, Engineer, QA),
  each a fresh session per `_docs/process.md`.
- **PM input/output:** turned the owner's rules into checkable criteria by
  reading `openapi.yaml`, `mock-seed.ts`, `mock.ts`, and `validation.ts`
  first. Made explicit design decisions the backlog left implicit: `Store`
  as an `abc.ABC` (not `Protocol`) so issue #6's SQLAlchemy store fails
  loudly if it misses a method; seed data in `backend/app/seed.py` as
  storage-agnostic plain data so #6 can reuse it; a server-side session
  record alongside the JWT so logout actually revokes a token. Resolved a
  real disagreement between the contract (413/415 on upload) and the
  frontend mock (400 for both) in the contract's favor, per the owner's
  instruction to check `openapi.yaml`, not guess. Found and flagged — but
  explicitly left unfixed, per the issue's own constraint — a gap in
  `openapi.yaml` itself: `approveRound` doesn't document a `404` response
  for an unknown guest token, unlike every other guest endpoint.
- **Engineer input/output:** built the full backend — six routers, Pydantic
  schemas for every contract type, the `Store` ABC + `InMemoryStore`, seed
  data matching the frontend mock's demo accounts/rooms exactly, JWT +
  bcrypt auth with session revocation, and every business rule (sequential
  pin numbering, reopen-on-guest-reply, approve-reopens-on-new-pin,
  closed-room 403s, upload 413/415, ETag/Cache-Control on image bytes,
  text/plain export). Hit and documented one real-world dependency
  conflict: bcrypt 5.0 broke passlib 1.7.4's import-time self-test, fixed
  with a `bcrypt<4.1` pin, reported rather than silently patched around.
  Wrote 73 tests including named cases for every business rule and a
  dedicated contract-coverage test.
- **Review:** QA re-ran the full test suite independently (73/73, twice, via
  two different invocation paths), ran the live server and curl'd every
  auth/ownership/business-rule claim itself rather than trusting the
  engineer's report (cross-owner 404s, cross-room guest-token 404s, logout
  revocation, the approveRound 404 gap, every closed-room rejection),
  grepped for stray `InMemoryStore` imports to confirm the interface
  boundary actually holds, and checked the installed dependency versions
  against the engineer's stated justification for the bcrypt pin.
- **Verification:** `make test` → 73 passed, 0 failed (engineer and QA, run
  independently); `test_openapi_contract.py` confirmed to actually diff
  `openapi.yaml`'s (path, method) pairs against `app.openapi()`; `make run`
  + `GET /health` → 200; live curls against the running server for seed
  data, auth, ownership, and every listed business rule. QA verdict: PASS
  on all 6 acceptance-criteria sections. Orchestrator closed issue #4 and
  pushed `220f89a` to `main`.

## 2026-10-12 — Issue #5: Connect frontend and backend

- **Tool:** Claude Code, orchestrator + PM + two engineer passes + two QA
  passes (a real FAIL/fix/re-verify loop per `_docs/process.md` step 5),
  each a fresh session.
- **PM input/output:** read `openapi.yaml`, `http.ts`, the backend's CORS
  config, and issue #4's grooming history before writing criteria. Found,
  by reading code rather than assuming, that Vite doesn't load a root-level
  `.env` by default and that `<img src>` needs an absolute URL the backend's
  relative `RenderImage.url` doesn't provide. Made a deliberate, justified
  call to document a two-terminal recipe in the README instead of adding a
  `make dev` target, to avoid cross-platform process-lifecycle risk. Made
  "which test-scenario steps need a human browser check" an explicit,
  required part of QA's output for this issue, since no browser automation
  tool is available to these agents.
- **Engineer input/output (pass 1):** fixed Vite's `envDir`, rewrote
  relative image URLs to absolute inside `http.ts` only (left UI components
  untouched), added the `approveRound` 404 doc fix to `openapi.yaml`
  (backend already behaved correctly — documentation-only), added 401
  token-clearing, wrote `http.test.ts` for request shaping, and ran a full
  curl-based walkthrough of test-scenario steps 1–7 against the real
  backend. Surfaced, but did not unilaterally fix (correctly flagged
  instead), a real finding outside what the issue text assumed: the actual
  `npm run dev` port is 8080 (from the Lovable config wrapper), not Vite's
  assumed default 5173, and `CORS_ORIGINS`'s default didn't cover it.
- **Review (QA pass 1): FAIL.** QA followed up on the engineer's flagged
  finding instead of treating it as a nitpick — confirmed live that the
  real dev server's actual origin was CORS-blocked by default, which
  defeats this issue's literal goal (frontend talks to backend) regardless
  of which port number the issue text happened to assume. Correctly
  distinguished "the issue text's example was wrong" from "the underlying
  acceptance criterion is satisfied," and failed on the latter.
- **Engineer input/output (pass 2):** chose to pin the dev server to
  `5173` with `strictPort: true` in `vite.config.ts` (fail loudly on
  conflict) rather than chase the wrapper's non-deterministic port
  fallback with a `CORS_ORIGINS` change, reasoning that a stable pinned
  port keeps every existing doc/config correct with one small change.
  Verified live against the real backend.
- **Review (QA pass 2): PASS.** Re-verified the entire issue fresh (not
  just the fix) — restarted the dev server from a clean port, confirmed
  `strictPort` actually fails loudly on conflict rather than silently
  drifting, re-ran the full curl walkthrough with fresh data, and reverted
  an incidental line-ending-only diff on a generated file (`routeTree.gen.ts`)
  twice to keep the tree clean.
- **Verification:** backend `pytest` 73 passed (both QA passes); frontend
  `vitest` 39 passed across 5 files with no `.env`/backend running (mock
  regression guard holds); `npm run build` succeeds; live CORS curl check
  against the real, pinned port returns 200 with the correct
  `Access-Control-Allow-Origin`. QA's required step-by-step breakdown of
  test-scenario steps 1–7 (curl-verified vs. needs-human-browser-check) is
  recorded on the issue. Orchestrator reverted the stray generated-file
  diff, closed issue #5, and pushed all 5 commits to `main`.

## 2026-10-12 — Issue #16: Human browser QA after #5 (sign-up, image rendering, dev-server noise)

- **Tool:** Claude Code, orchestrator + PM + Engineer + QA, each a fresh
  session per `_docs/process.md`. Issue created from the owner's own manual
  Chrome walkthrough of `_docs/test-scenario.md` against the real backend.
- **PM input/output:** root-caused as much as possible from reading code
  alone before handing off. For the studio 401, confirmed with certainty
  that a bare `<img src>` can't send a bearer header, and chose
  authenticated-fetch-to-object-URL over a signed query token specifically
  because a signed token would break the stable cache key issue #4's
  `ETag`/`Cache-Control` headers rely on. For the stranger "guest returns
  200 but still shows broken" report, ruled out three hypotheses by reading
  code (no conditional-GET/304 logic exists at all; the URL-rewrite already
  covers guest rooms and is tested; the seed JPEGs are real valid files),
  then — rather than guessing past that point — left a priority-ordered
  list of what to check live, explicitly flagging that reading alone
  couldn't settle it.
- **Engineer input/output:** implemented the sign-up mode toggle (extracted
  to a testable pure function, since this repo's jsdom setup can't render
  full routes), the contract-first prose update, and the studio
  object-URL fix with a new `useImageSrc` hook (the one deliberate,
  issue-sanctioned exception to issue #5's "don't touch components" rule).
  For the guest investigation, worked through the PM's priority list rather
  than assuming: found the guest endpoint itself was fine on every live
  check, and landed on a plausible explanation (a dev server started before
  `.env` existed would have silently served `MockApiClient`) that it
  couldn't fully re-prove after the fact — so, per the issue's own
  instruction for exactly this case, applied the documented fallback
  (routing guest images through the same mechanism as studio) rather than
  declaring the bug fixed without evidence. Reproduced the dev-server abort
  trace live, confirmed no supported suppression config exists, and
  documented it in `frontend/README.md` instead.
- **Review:** QA treated the investigation as the highest-scrutiny part of
  the review — independently re-ran the engineer's own verification method
  for the stale-dev-server theory, confirmed via diff (not the PR
  description) that guest images really do use the fallback mechanism and
  that the guest endpoint's contract is genuinely unchanged, and curled
  both image endpoints itself for seeded and freshly-uploaded JPG/PNG
  files. Found and reported one minor, real, unflagged issue (an in-flight
  object-URL fetch that resolves after cancellation is never revoked) —
  judged non-blocking rather than a FAIL, and left unfixed per its own
  "report, don't fix" mandate.
- **Verification:** `make test` → 73 passed (backend); `make
  frontend-test` → 48 passed across 6 files (frontend, mock still
  selectable); `npm run build` succeeds; live curl checks against the real
  backend for 401-without-token/200-with-token (studio) and 200
  (guest, seeded + fresh uploads). QA verdict: PASS, with the required
  verified-vs-needs-human-browser-check breakdown recorded on the issue
  (visual image rendering, the resize-keeps-pin-positioned check, and the
  sign-up form's appearance all still need a human browser pass).
  Orchestrator closed issue #16 and pushed all 5 commits (2 of them the
  repo owner's own direct `.gitattributes`/decisions.md commits, made
  outside this session) to `main`.

## 2026-10-13 — Issue #6: Persistence with SQLAlchemy

- **Tool:** Claude Code, orchestrator + PM + Engineer + QA, each a fresh
  session per `_docs/process.md`.
- **PM input/output:** read `store/interface.py` and `store/memory.py`
  closely before writing criteria, confirming the business rules
  (sequential pin numbering, reopen-on-reply, closed-room rejections,
  session-based logout revocation) live in router code calling plain
  `Store` primitives — not in the store itself — which meant the existing
  issue #4 test suite, unchanged, could serve as the drift-detector proving
  the new store behaves identically. Confirmed the frontend-asset-to-seed-
  image mapping by matching ids between `seed.py` and `mock-seed.ts`,
  not by eyeballing the photos. Caught an edge case the backlog missed: a
  SQL store has no guaranteed row order without an explicit `ORDER BY`,
  unlike `InMemoryStore`'s free dict-insertion ordering — made this an
  explicit, separate criterion. Made firm, stated calls on sync SQLAlchemy,
  keeping `InMemoryStore` as an unused reference implementation rather than
  deleting it, and a `TEST_DATABASE_URL` opt-in with no partial-skip state
  for the Postgres test path.
- **Engineer input/output:** built the full SQLAlchemy storage layer
  (models, engine, store) against the `Store` ABC, wired it in as the
  app's real store, replaced the three placeholder seed images with the
  frontend's real Lovable renders (one-way copy, `seed.py` untouched), and
  added dependencies via `uv add`. Found and fixed a real bug its own
  first-draft implementation introduced: seeding unconditionally on every
  `SQLAlchemyStore.__init__` crashed on a second restart against a
  persistent database — exactly the scenario the issue's own goal
  describes — fixed by seeding only when the database is empty, and
  flagged the deviation explicitly rather than silently patching it in.
  Reported honestly, rather than skipping silently, that the Postgres path
  couldn't be verified in its sandbox (no reachable Docker daemon or
  `psql`).
- **Review:** QA didn't just read the fix, it reproduced the
  restart-persistence proof itself end-to-end (start server, create a
  room, kill every process on the port, restart, confirm no duplicates/no
  crash), wrote a throwaway script to prove the `Store` ABC's
  "missing-method fails loudly" guarantee actually holds for the real
  class, and ran `sha256sum` to confirm the replacement seed images are
  genuinely byte-for-byte identical to the frontend's source files rather
  than just same-named. Independently hit the same Postgres-unreachable
  wall and correctly treated it as an environment constraint, not a FAIL,
  consistent with how issues #5/#16 handled checks outside the pipeline's
  reach.
- **Verification:** `make test` → 75 passed, 0 failed (full issue #4 suite
  intact plus two new seed-image tests, run independently by engineer and
  QA); live restart-persistence proof reproduced twice; seed image
  checksums confirmed; Postgres path explicitly marked
  could-not-verify/environment-constraint by both passes. QA verdict: PASS.
  Orchestrator closed issue #6 and pushed the two implementation commits
  (plus one unrelated commit the repo owner made directly between sessions,
  moving `make-it-better.md` out of the public repo) to `main`.

## 2026-10-13 — Issue #7: Image upload and serving

- **Tool:** Claude Code, orchestrator + PM + Engineer + QA, each a fresh
  session per `_docs/process.md`.
- **PM input/output:** framed this explicitly as a verify-and-harden pass
  rather than a rebuild, since most of the original scope (JPG/PNG
  validation, the 15 MB limit, ETag/Cache-Control) already shipped in
  issues #4/#16. Read `useImageSrc.ts` closely enough to name the exact
  leak mechanics (an object URL created by an in-flight fetch that resolves
  after the effect already cancelled was being discarded instead of
  revoked) and wrote the fix as literal code in the issue, not a vague
  description. Did the same for the stale-cache fix (`cache: "no-cache"`,
  explicitly not `"no-store"`, with the reasoning for the distinction
  spelled out). Confirmed, by reading the backend and the contract, that no
  backend change was needed at all — stated that plainly rather than
  inventing busywork.
- **Engineer input/output:** confirmed the Verify section by reading code
  and running the existing suite untouched, then applied both fixes
  exactly as specified, plus three new vitest cases for the leak fix
  covering late resolution, the normal path, and rapid image switching.
  Touched only the four files the issue named.
- **Review:** QA went beyond reading the new tests — it actually reverted
  the leak fix in a scratch copy and re-ran the new test suite to confirm
  it would genuinely catch the regression (2 of the 3 new cases failed as
  expected; the case that doesn't exercise the cancelled branch correctly
  still passed, proving the coverage isn't tautological), then restored the
  fix and confirmed a clean tree. Also confirmed via `git log --stat` that
  zero backend files were touched, matching the "no backend changes
  expected" constraint.
- **Verification:** `make test` → 75 passed (backend, unchanged); `make
  frontend-test` → 51 passed across 7 files (48 existing + 3 new); `npm run
  build` succeeds. QA verdict: PASS. Orchestrator closed issue #7 and
  pushed both commits to `main`.

## 2026-10-13 — Issue #8: Dockerfile and Docker Compose

- **Tool:** Claude Code, orchestrator + PM + Engineer (resumed once
  mid-task after it stalled waiting on a background process) + QA, each a
  fresh session per `_docs/process.md`.
- **PM input/output:** read the actual frontend build-output path, the
  current base-URL selection logic, and the SQLAlchemy store before
  writing criteria. Found a real, previously-unnoticed bug while reading
  `index.ts`: an explicitly-empty `VITE_API_BASE_URL` (exactly what the
  Docker build needs for same-origin requests) was falling through to
  `MockApiClient` because the code used a truthiness check, not an
  `undefined` check — made fixing this an explicit, in-scope criterion
  rather than letting the container ship broken. Named exact Dockerfile
  stage contents, exact compose service configs, and a Postgres
  verification mechanism (a `profiles: ["test"]` compose service) chosen
  specifically so Postgres is never exposed to the host in any invocation.
  Flagged a datetime timezone mismatch between the store's parsed
  timestamps and the schema's naive columns as a risk to watch for, not
  asserted as a confirmed bug.
- **Engineer input/output:** this pass stalled mid-task (a background
  `npm install` wait went unresolved and the agent's turn ended on a stray
  status line with nothing committed) — the orchestrator noticed no
  commits/comment had landed, checked the repo directly, and resumed the
  same agent with its own context intact rather than restarting from
  scratch. On resume, it built the full two-stage image, the compose
  stack, and the SPA-fallback backend route; found and fixed a real bug
  the PM's flagged risk didn't predict (a different one): seeding all rows
  in one flush with no ORM relationships let SQLite's deferred FK checks
  pass silently while Postgres rejected it with a real
  `ForeignKeyViolation` — fixed by flushing in parent-then-child batches.
  Disclosed two deliberate deviations from the issue's literal text
  (`npm install` instead of `npm ci`, since the committed lockfile is
  missing Linux-only optional entries; copying `openapi.yaml` into the
  image for the test profile) instead of silently reinterpreting scope.
- **Review:** QA treated both disclosed deviations as things to verify, not
  accept on faith — reproduced the exact `npm ci` failure in a scratch
  build, then regenerated a Linux-complete lockfile to confirm `npm ci`
  *would* work against it (judging the deviation justified under this
  issue's own constraints, but flagging the lockfile regeneration as a
  real follow-up). It also reverted the engineer's FK-ordering fix and
  reran the Postgres suite to confirm the bug was genuinely real, not
  just plausible-sounding.
- **Verification:** `docker build` from scratch succeeds; the real
  Postgres verification path (`docker compose --profile test run --rm
  backend-test`) passes 81/81, run independently by both engineer and QA,
  with QA additionally proving it would have failed without the fix;
  `docker compose up -d --build --wait` brings up a healthy stack, serving
  the demo rooms/photos at `localhost:8100` with Postgres unreachable from
  the host; `_docs/test-scenario.md` steps 1–8 driven against the live
  stack via script, including step 8's restart-persistence (`docker
  compose restart app`) — now genuinely provable for the first time, since
  this is the first issue where the running app is backed by real
  Postgres instead of SQLite or memory; `docker compose down -v` leaves no
  containers/volumes. Non-Docker regression: `make test` 81 passed
  (SQLite), `make frontend-test` 51 passed, `npm run build` succeeds. QA
  verdict: PASS. Orchestrator closed issue #8 and pushed all 6 commits to
  `main`.

## 2026-10-13 — Issue #9: Integration tests

- **Tool:** Claude Code, orchestrator + PM + Engineer + QA, each a fresh
  session per `_docs/process.md`.
- **PM input/output:** caught and corrected two inaccuracies in the task
  description before they became wasted test coverage. First, the brief
  asked for an "ETag/304" upload scenario — the PM re-read
  `serializers.py` directly, confirmed (again, consistent with issues
  #7/#16) that no conditional-GET logic exists anywhere in this codebase,
  and rewrote the criterion to test ETag presence/stability only, not a
  304 that was never built. Second, the brief assumed issue #8's QA pass
  left behind a reusable verification script — the PM checked the repo and
  issue #8's own comments and found that verification was inline,
  never saved, and said so plainly rather than pointing the engineer at a
  file that doesn't exist. Also made an explicit call on the bundled
  lockfile fix: regenerate once and commit, not regenerate on every
  Docker build, since the latter would undo the determinism `npm ci`
  exists for.
- **Engineer input/output:** built the full `integration/` suite (8 test
  files, no backend imports, independent per-test setup), the
  restart-persistence test (a real `docker compose restart app`, polling
  `/health` with a bounded retry), `make integration`, `docs/testing.md`,
  and the one-time lockfile regeneration that let the Dockerfile go back
  to `npm ci`. Along the way it caught its own regression: running `make
  frontend-test`'s `npm install` silently reverted the lockfile fix mid-
  session — it noticed via `git status`, restored the file, and documented
  the risk in `docs/testing.md` instead of letting a future session
  rediscover it blind. Also disclosed an honest timing nuance rather than
  overselling the fail-fast requirement: the stack-down failure is
  readable and never hangs, but takes ~59s end-to-end on this
  Windows/Docker Desktop setup, not literally "a few seconds."
- **Review:** QA treated both engineer-disclosed nuances as things to
  verify, not take on faith — reproduced the lockfile-reversion risk
  itself (confirmed `npm install` really does strip the Linux-only
  entries again), and used `docker inspect`'s container start timestamps
  to independently confirm the persistence test's restart was genuinely
  real (app's `StartedAt` ~8s old, postgres untouched at 13 minutes
  uptime) rather than a no-op. Judged the ~60s fail-fast timing an
  acceptable engineering tradeoff, not a gap, while still flagging it as
  worth a documentation caveat.
- **Verification:** `make integration` → 15/15 passing against the live
  compose stack (run independently by engineer and QA); `docker build
  --no-cache` with `npm ci` succeeds from a clean state (verified by both
  passes); `make test` 81 passed (SQLite), `make frontend-test` 51 passed,
  `npm run build` succeeds, the Postgres path 81 passed. QA verdict: PASS.
  Orchestrator closed issue #9 and pushed all 3 commits to `main`.

## 2026-10-13 — Issue #10: End-to-end test with Playwright

- **Tool:** Claude Code, orchestrator + PM + Engineer + QA, each a fresh
  session per `_docs/process.md`. First issue in this project driving a
  real browser (Playwright's own Chromium, not a mocked/dev-server
  frontend) against the real Compose stack.
- **PM input/output:** read the actual frontend route components before
  writing a single UI interaction into the criteria, rather than inventing
  plausible-sounding selectors. Found that "copy guest link" isn't a
  persistent DOM link at all — it's a clipboard-write plus a toast whose
  visible text happens to be the same URL — and wrote the test's real
  mechanism instead of a stand-in. Pulled exact DOM strings (the closed-
  room banner, the "approved by" template, the literal lowercase
  `"resolved"` text) straight from the components so the test couldn't
  silently assert invented wording. Designed the `make e2e` start/teardown
  symmetry (leave the stack exactly as found) as an explicitly testable
  pair of scenarios, not just a described intention.
- **Engineer input/output:** built both spec files and the orchestration
  script per the groomed spec, fixed two genuine test-side selector bugs
  against the real running app (a thumbnail `<img>` shadowing the main
  stage image; a dialog overlay still intercepting clicks mid-exit-
  animation) rather than loosening the assertions. Found a real
  acceptance-criterion impossibility and handled it exactly per
  `_docs/team/software-engineer.md`'s rule — commented on the issue with
  code/contract evidence instead of silently editing the criterion or
  adding an unrequested studio pin-creation feature: the app has no
  studio-side pin-creation path at all (confirmed via both the route
  wiring and `openapi.yaml`), so the resize test places its pin through a
  guest context while keeping everything else as specified.
- **Review:** QA independently re-derived the same conclusion on the
  flagged deviation (re-reading the same route file and contract) before
  accepting it, rather than taking the engineer's citation at face value.
  Ran the full suite three times to rule out flakiness, verified both
  directions of the start/teardown symmetry itself, and deliberately broke
  a *different* assertion than the engineer had to confirm the
  trace/report mechanism isn't something that only works for one specific
  failure.
- **Verification:** `npx playwright test` — 2/2 passing, three consecutive
  runs, no flakiness (18–30s each); `make e2e` symmetry confirmed both
  ways (stack-already-up leaves the same container IDs; stack-down starts,
  runs, and tears back down to empty); a real `trace.zip`/HTML
  report produced and inspected on an injected failure, then cleanly
  reverted; `make test` 81 passed, `make frontend-test` 51 passed, `npm run
  build` succeeds. QA verdict: PASS. Orchestrator closed issue #10 and
  pushed both commits to `main`.

## 2026-10-14 — Issue #11: CI pipeline

- **Tool:** Claude Code, orchestrator + PM + Engineer (two passes, one
  blocked on a scope decision) + QA, each a fresh session per
  `_docs/process.md`. First issue where the engineer pushed directly to
  `main` mid-work (twice), since verifying a GitHub Actions workflow is
  only possible by actually triggering a run on GitHub's own
  infrastructure — pre-authorized by the orchestrator for this issue only,
  not a change to the project's normal push discipline.
- **PM input/output:** made two explicit design calls instead of leaving
  them for the engineer to improvise: a matrix for the backend job's two
  database legs (so a Postgres-only failure shows as its own distinct
  check rather than hiding behind a single `backend` red/green), and
  reusing the existing `make e2e` script for the stack job's Playwright
  step rather than calling Playwright directly — correctly predicting that
  `run.mjs`'s own stack-detection would no-op cleanly once the `stack`
  job's `docker compose up --wait` had already brought the stack up.
  Scoped the "fix what only breaks on GitHub's runners" allowance
  narrowly and explicitly, which is exactly what let the engineer
  recognize the later TypeScript failure as outside that allowance rather
  than quietly folding it in.
- **Engineer input/output:** got the workflow running on a real push and
  hit a genuine blocker on the first try — wiring `tsc --noEmit` into CI
  for the first time surfaced pre-existing type errors in four frontend
  test files, which reproduced identically on a local run too (not a
  Linux-runner quirk). Correctly recognized this as outside the issue's
  own pre-approved allowance and stopped to ask rather than either
  silently fixing it or silently ignoring it — a real scope decision that
  was the repo owner's to make, not the agent's. On approval, fixed the
  four files with non-null assertions and a properly-typed test fake,
  verified the fix changed no actual assertion, and pushed again to a
  fully green run exercising every job including a live `docker compose
  build`/`up`, `make integration`, and a fresh Chromium download for
  `make e2e`.
- **Review:** QA didn't just trust the "green run" claim — it pulled the
  actual job logs from both GitHub Actions runs via the API, confirmed the
  first run's failure log contained the exact 10 error lines the engineer
  named, and confirmed the second run's `stack` job log showed genuine
  pytest/Playwright output (not a cache hit or a skip) — real `collected N
  items`/`N passed` lines and a live Chromium download progress bar. Also
  fetched the live README badge's SVG directly and checked its text
  content said "passing," rather than trusting the markdown's presence.
- **Verification:** Real GitHub Actions run
  https://github.com/MargaritaV33/pinpoint/actions/runs/38536296305 — all
  4 jobs (`backend (sqlite)`, `backend (postgres)`, `frontend`, `stack`)
  green, independently confirmed via job logs by QA. Local:
  `npx tsc --noEmit` clean, `make frontend-test` 51/51. QA verdict: PASS.
  Orchestrator restored a local lockfile drift from QA's own `npm install`
  (the known issue #9 reversion risk, harmless and already documented),
  closed issue #11 — both commits (`d93f8cd`, `4c94587`) were already on
  `origin/main` from the engineer's required mid-work pushes, so nothing
  further needed pushing.

## 2026-10-14 — Issue #12: Deployment to Render

- **Tool:** Claude Code, orchestrator + PM + Engineer + QA, each a fresh
  session per `_docs/process.md`. First issue in this project with a hard
  boundary built into its own definition of done: no agent has Render
  dashboard access, so the deliverable stops at a committed, locally-
  verified Blueprint + docs, with the actual "Apply" click explicitly
  handed off as a numbered list for the repo owner.
- **PM input/output:** found a real, would-be-silent production bug before
  any code was written — Render's `fromDatabase` connection string is a
  bare `postgresql://` URL, but this backend only has `psycopg[binary]`
  installed, not `psycopg2`, which is SQLAlchemy's default driver for that
  bare scheme. Without a fix, the app would have deployed successfully and
  then crashed on boot with `ModuleNotFoundError`. Designed the fix
  entirely inside `render.yaml`'s `dockerCommand` (a `sed` rewrite to
  `postgresql+psycopg://`) rather than touching `backend/`, since this
  issue's own constraints rule out application-code changes. Also went
  var-by-var through `backend/app/config.py`'s settings to decide which
  needed an explicit `render.yaml` entry versus which could rely on their
  existing defaults, rather than copying every `.env.example` var
  reflexively.
- **Engineer input/output:** built `render.yaml` and `docs/deployment.md`
  exactly to spec, then — correctly recognizing the task's own boundary —
  did not attempt to open a dashboard or claim a deployment happened.
  Instead ran every check that *was* locally possible: parsed the YAML,
  executed the dialect-rewrite `sed` command standalone against both URL
  schemes, matched every env var key against real `Settings` fields, and
  posted the exact 6-step manual hand-off as a clearly-labeled list on the
  issue rather than performing or pretending to perform it.
- **Review:** QA went one level deeper than the engineer's own
  verification — rather than trusting the isolated `sed` line, it
  extracted the real `dockerCommand` string, modeled how Render actually
  consumes that field (tokenize-then-exec, no extra shell layer), and ran
  it end-to-end via `subprocess` with a mocked `DATABASE_URL` for both
  connection-string schemes, confirming the fix survives real execution.
  It also caught and documented a test-harness pitfall for anyone
  re-verifying this later (naively running the command through an extra
  shell layer double-expands the variable and looks broken when it isn't).
  Confirmed the hand-off list was present and correctly labeled as not
  performed.
- **Verification:** `render.yaml` parses as valid YAML; the dialect fix
  verified correct for both `postgres://` and `postgresql://` inputs, by
  both engineer and QA, with QA's deeper end-to-end execution test; every
  env var key matched a real config field; `docs/deployment.md` and the
  README pointer matched the issue's exact required content and style. No
  live deployment was attempted or claimed — correctly out of scope for
  this issue. QA verdict: PASS. Orchestrator closed issue #12 and pushed
  `524b2bc` to `main`.

## 2026-10-14 — Issue #12 reopened: Render deploy crashed in production

- **Tool:** Claude Code, orchestrator + Engineer + QA (no PM pass — the
  repo owner reported the production failure with the root cause and the
  exact required fix already specified, so the lifecycle ran Engineer →
  QA directly, per explicit instruction).
- **What broke:** the real Render deploy crashed on boot —
  `sh: 1: DATABASE_URL="postgresql://...@dpg-.../pinpoint_xxuj" uv run
  uvicorn ...: not found`, exit code 127. `render.yaml`'s `dockerCommand`
  override, verified locally by simulating the command string in
  isolation (a `subprocess`/`shlex` test), had never actually been run
  inside the real built image — the one check that would have caught this
  before it reached production.
- **The lesson, as the repo owner asked to have it recorded:** issue #12's
  original QA pass simulated the deploy command correctly in isolation and
  still missed the real failure, because the bug lived in the gap between
  "this shell command is syntactically and semantically correct" and
  "this is actually how the runtime platform invokes it." Executing a
  command string outside its real execution context — even faithfully,
  even with real subprocess calls — is not the same as running the real
  artifact (the built Docker image, with Render's actual invocation
  mechanism) end to end. The fix for *this* issue was to stop giving
  Render anything to mis-invoke at all (remove the override, let the
  Dockerfile's own `CMD` be the only thing that ever starts the
  container) — but the broader lesson is that a production platform's own
  invocation semantics are not something a local simulation can stand in
  for; only actually running the artifact in something resembling the
  real target does.
- **Engineer input/output:** implemented the prescribed fix (remove
  `dockerCommand`; move the `postgres://`/`postgresql://` →
  `postgresql+psycopg://` normalization into a `Settings` field validator
  in `backend/app/config.py`, traced through the real call chain to
  confirm one validator covers every consumer; added a 4-case unit test)
  — and, while doing so, corrected the originally-stated root cause rather
  than taking it on faith: `uv` genuinely is present in the runtime image,
  and the Dockerfile's own `CMD` runs fine unmodified. The actual defect
  was narrower than first diagnosed (Render's command-override mechanism
  itself), though the prescribed fix eliminates it regardless of the exact
  mechanism. Verified this time by actually building and running the real
  image with a bare `postgresql://` URL against a real Postgres, with no
  command override — confirmed the container starts clean and a real
  login succeeds end to end, not simulated.
- **Review:** QA independently re-derived the same root-cause correction
  from its own fresh evidence (found `uv` in the image, inspected the
  Dockerfile's real `Config.Cmd`, ran the unmodified image successfully)
  rather than repeating the engineer's claim, and re-ran the full real
  Docker build+run verification itself end to end, going as far as the
  engineer did (a real login against the seeded account). Surfaced one
  unrelated but genuinely useful finding along the way: `backend/.python-
  version` pins 3.11 while the Dockerfile builds on `python:3.12-slim`,
  so `uv run` resyncs the venv from scratch on every cold start — a real
  cost on Render's free plan, which spins down and re-starts cold, worth
  its own follow-up issue.
- **Verification:** real `docker build` + `docker run` (no mocking, no
  command simulation) against a real compose Postgres, by both engineer
  and QA independently — container starts clean, `/health` returns 200,
  a real demo-account login succeeds through the normalized URL;
  `backend/tests/test_config.py`'s 4 cases pass; full suite 85/85. QA
  verdict: PASS. Orchestrator removed a leftover empty test volume QA's
  sandbox couldn't delete, closed issue #12, and pushed `406a48d`,
  `5117c40` to `main`. The actual Render redeploy (applying this fix in
  production) is, as before, the repo owner's own action to take.

## 2026-10-14 — Issue #13: Continuous deployment

- **Tool:** Claude Code, orchestrator + PM + Engineer + QA, each a fresh
  session per `_docs/process.md`. Same hard verification boundary as
  issue #12 — no agent has Render dashboard access or the real
  `RENDER_DEPLOY_HOOK_URL`/`PUBLIC_URL` secrets, so this issue's own "done"
  deliberately excludes a real triggered deploy.
- **PM input/output:** before writing a single criterion, researched
  whether Render needed a Docker build-arg to expose the deployed git SHA
  — and found it already injects `RENDER_GIT_COMMIT` automatically at both
  build and runtime, with zero Blueprint config. This single finding
  eliminated an entire planned Dockerfile change the original task brief
  assumed was necessary. Also caught that the brief's proposed
  `autoDeploy: true|false` key is deprecated in favor of
  `autoDeployTrigger`, and confirmed Render's undocumented-to-the-brief
  default (`commit`) means this issue's `off` value is a real behavior
  change, not a restatement of an existing no-op. Set the smoke-test poll
  budget at 10 minutes rather than the brief's example 2 minutes, with the
  reasoning spelled out in the issue so a future pass doesn't silently
  shorten it back into flakiness.
- **Engineer input/output:** implemented the health-check change, the
  `deploy` job, the `render.yaml` key, and the release-process doc
  exactly to spec. Found and fixed one test that the `/health` shape
  change genuinely broke (`test_frontend_fallback.py`), outside the
  issue's named file list but a direct, necessary consequence of the
  change rather than scope creep. Verified the shell poll loop's logic by
  extracting it into a standalone harness with a mocked `curl`/`jq` rather
  than only reading it, covering the success, timeout, and
  stale-commit-never-matches cases.
- **Review:** QA re-ran the engineer's loop-harness approach independently
  and extended it with three failure modes the engineer hadn't tried (a
  non-JSON response body, a `curl` connection failure, an HTTP 500) to
  confirm the guards degrade gracefully rather than crashing or falsely
  succeeding. On the one open technical question flagged by the engineer
  — whether `autoDeployTrigger: off` is misinterpreted as a YAML boolean
  — QA didn't just reason about it, it fetched Render's own published
  Blueprint JSON schema and confirmed `autoDeployTrigger` is a strict
  string enum in Render's own validation, not a boolean, settling the
  question with external evidence rather than inference.
- **Verification:** `make test` → 86 passed (both passes, independently);
  both `ci.yml` and `render.yaml` confirmed to diff only the intended new
  lines; the deploy job's loop logic verified correct under 4+ scenarios
  by two independent harnesses. No real deploy was attempted or claimed —
  correctly out of scope pending the repo owner's secret/variable setup.
  QA verdict: PASS. Orchestrator closed issue #13 and pushed `9914f3f`,
  `d8e5494`, `328d819` to `main`.

## 2026-10-14 — Issue #17: Align Python version between .python-version and the Dockerfile

- **Tool:** Claude Code, orchestrator + PM + Engineer + QA, each a fresh
  session per `_docs/process.md`. Follow-up from a side finding QA
  surfaced during issue #12's incident fix (venv resync cost on every
  cold start), filed and run as its own issue.
- **PM input/output:** traced the actual resync mechanism through the
  real Dockerfile line numbers rather than repeating the task brief's
  assertion — and in doing so corrected a real error in the brief itself:
  the baked venv lives at `/app/backend/.venv` (because `uv sync` runs
  with `cd backend` while `WORKDIR` is `/app`), not `/app/.venv` as
  assumed. Also reasoned explicitly about which of the two prescribed
  changes was load-bearing: the `CMD` change alone eliminates the
  cold-start cost (bypassing `uv run` entirely means there's no
  sync-check to trigger regardless of version alignment), while the
  version bump is separately worth doing because the same image's
  legitimate `uv run pytest` path (`backend-test`) would otherwise still
  pay the same resync cost. Checked CI's own Python setup and confirmed
  it was already consistent (3.12) and never part of the problem, closing
  off a scope question before it could become unnecessary work.
- **Engineer input/output:** a precise two-line fix across two files.
  Caught and fixed its own near-miss before it mattered: a first commit
  draft accidentally included a GitHub auto-close keyword ("Closes #17"),
  which would have closed the issue out from under QA on push to `main` —
  noticed and amended before any push happened. Verified with real,
  unsimulated Docker runs: confirmed the baked interpreter now matches,
  confirmed zero uv-sync output in a running container's logs (the one
  check that actually proves the fix), and incidentally discovered a
  stale local image tag masking the fix on first attempt — caught it via
  the unexpected 3.11 download in the logs, force-rebuilt, and got the
  real signal.
- **Review:** QA independently reran every verification step from a
  clean/no-cache state rather than trusting the engineer's run (including
  its own forced rebuild of the `backend-test` service, the same stale-
  cache trap the engineer had just hit), confirmed the commit message
  carried no auto-close keyword, and swept the full container log output
  itself for sync-related lines rather than trusting a summary.
- **Verification:** real `docker build`/`docker run` (no mocking) by both
  passes — interpreter version confirmed `3.12.x`, zero uv-sync output at
  container start, Compose and the `backend-test` profile both green at
  86/86, local `make test` 86/86. QA verdict: PASS. Orchestrator removed
  a leftover verification image, closed issue #17, and pushed `ec6f564`
  to `main`.

## 2026-10-14 — Issue #14: Documentation pass

- **Tool:** Claude Code, orchestrator + PM + Engineer (two passes, one
  blocked on a QA FAIL) + QA (two passes), each a fresh session per
  `_docs/process.md`. The issue this entry describes is itself the
  documentation this entry lives in — `docs/ai-usage-report.md`'s own
  `## Summary` section and this `## Appendix` heading were both added as
  part of this issue.
- **PM input/output:** grounded every diagram, table, and claim in real,
  current files rather than the task brief's own assertions — read
  `backend/app/store/sqlalchemy/models.py` directly for the data model
  (5 real tables, not invented fields), `openapi.yaml` for the auth-flow
  wording, and every env/Compose/Render config file for the environment
  matrix. Caught that the README's existing "Status: specification and
  backlog" line was stale and made removing it an explicit criterion.
  Made the "verify every command" requirement literal and enumerated (9
  named commands with required exit codes/output) rather than a vague
  "check the README looks right."
- **Engineer input/output:** rewrote all four docs and ran the full
  enumerated verification list for real — including a complete
  `make up`/`make integration`/`make down`/`make e2e` cycle — rather than
  writing plausible-sounding prose. No real application bug surfaced
  during verification, so none was fabricated to report.
- **Review (QA pass 1): FAIL.** QA re-ran every one of the 9 commands
  independently rather than trusting the engineer's recorded output, and
  additionally cross-checked the new `ai-usage-report.md` Summary's three
  named historical bug examples against the real closed-issue threads
  (`gh issue view 12/7/5 --comments`) instead of trusting the summary's
  own retelling — catching a real factual error: the summary claimed a
  CORS block caused the frontend to "silently" fall back to the mock,
  which is backwards (a CORS block fails loudly; the actual silent-mock
  bug and the CORS/port bug were two separate, sequential findings within
  issue #5, not one causal chain).
- **Engineer (follow-up):** rewrote the one bullet to describe the two
  real, sequential bugs accurately, re-checking the new text
  sentence-by-sentence against issue #5's actual thread before
  committing, and touched nothing else.
- **Review (QA pass 2): PASS.** Independently re-read issue #5's full
  thread itself (not just comparing the engineer's before/after text) to
  confirm the correction's every claim — fix order, the "mock already
  out of the picture" detail, the exact `400 Disallowed CORS origin`
  text, the `strictPort: true` fix — matches the real history, and
  confirmed via `git diff` that the fix commit touched only that one
  bullet, so the first pass's full 9-command verification still stood
  without needing to be rerun.
- **Verification:** all 9 enumerated README commands run and confirmed
  independently by both engineer and QA (`make sync`; `make run` + health
  check; frontend-against-real-backend login with demo credentials;
  `make test` 86 passed; `make frontend-test` 51 passed, with the known
  lockfile-reversion risk caught and restored by both passes; a full
  `make up`/`make down` cycle; `make up` + `make integration` 15 passed +
  `make down`; `make e2e` 2 passed, stack lifecycle symmetry preserved).
  The architecture doc's two Mermaid diagrams were actually rendered to
  SVG by QA to confirm valid syntax, not just read. No application code
  was touched by either engineer pass. QA verdict: PASS. Orchestrator
  closed issue #14 and pushed `c3fc8cd`, `6f0f3e0` to `main`.

## 2026-10-14 — Issue #15: Reproducibility check

- **Tool:** Claude Code, a single fresh QA agent (no PM, no Engineer, by
  deliberate request for this issue) plus the orchestrator handling the
  fixes directly — the first issue in this project run with that
  shortened lifecycle.
- **Method:** QA cloned `MargaritaV33/pinpoint` fresh into an isolated
  temporary folder outside the working repo, with explicit instructions
  not to read, copy, or reference anything from the existing checkout,
  any `.env` file, or prior context about the project — only the README
  and the docs it links, exactly as a first-time peer reviewer would
  encounter them. It then followed the README top to bottom, in the
  printed order, recording the exact command and exact output/error for
  every step rather than summarizing.
- **What it found.** 18 steps checked individually, 17 passed outright.
  The one real failure was in the README's own happy path, not an edge
  case: following the frontend section's `npm install` before the full-
  stack section's `make up`, on a non-Linux dev machine, leaves
  `frontend/package-lock.json` rewritten without its Linux-only optional
  entries — so `make up`'s Docker build fails at `npm ci` with a lockfile-
  mismatch error. The fix for this exact situation already existed,
  correctly described, in `docs/testing.md` from issues #9/#10 — but
  nothing in the README's own text pointed a first-time reader there, so
  following the README's own instructions in order broke on the README's
  own prescribed sequence. QA also surfaced 14 separate undocumented
  assumptions (A1–A14): no `git clone` step at all; `make`, and `uv`'s
  install mechanism and PATH behavior, named as prerequisites but not
  actually walked through; a PowerShell `&&`-syntax trap with no warning
  to use Git Bash instead; required-free ports and network access never
  stated; several smaller clarifications (`/` being 404-by-design, a
  harmless first-start reload warning, the Chromium download on `make
  e2e`'s first run).
- **Fixes:** all documentation-only, as instructed — no application code
  was touched, since none of the 18 findings traced to an actual code
  defect, only to the README's own gaps and ordering. Added the missing
  clone step, the full prerequisite list, the shell caveat, and — most
  importantly — the lockfile-restore step at every point in the README
  where an earlier `npm install` would otherwise silently break a later
  Docker build.
- **Verification, not just a rewrite:** rather than trusting that the
  documented fix command was correct, the orchestrator reproduced the
  exact failure in the same fresh clone QA had used (ran `npm install`,
  confirmed the lockfile was dirtied exactly as reported, applied the
  README's new restore step, then ran `make up` for real) and confirmed
  it built, came up healthy, and `/health` returned `200` — closing the
  loop on the one blocking gap with a real re-run, not an inference that
  the new wording would probably work.
- **Outcome:** issue #15 closed, the temporary clone deleted, `2522f6a`
  pushed to `main`. This is the first issue in the project where a single
  QA pass, run with zero prior context about the repo, served as its own
  complete verification loop — closer to what an actual outside reviewer
  will experience than any engineer-authored self-check could be.

## 2026-10-14 — Issue #18: Agent extension pack: skills and subagents

- **Tool:** Claude Code, orchestrator + PM + Engineer + QA, each a fresh
  session per `_docs/process.md`. The first meta-level issue in this
  project — its subject is the agent-orchestration tooling itself (the
  four subagent definitions and three skills this exact lifecycle already
  runs on), not the application.
- **PM input/output:** researched and grounded every skill's content in
  real files rather than inventing plausible-sounding process steps —
  confirmed `release`/`incident-response`'s claimed CI job order and
  rollback paths against the actual `.github/workflows/ci.yml` and
  `docs/release-process.md`, and confirmed there's genuinely no Render
  CLI anywhere in the repo before writing that absence into
  `on-call-responder`'s body as a stated fact. Made the "propose, never
  execute" requirement concrete rather than aspirational: a literal
  forbidden-action list in the subagent's body text, with a frontmatter
  tool restriction as best-effort reinforcement. Made a clean, reasoned
  call on where the agents/skills drift-check belongs — a standalone
  script plus one minimal, deliberately unrelated-to-deploy CI job,
  rather than forcing it into an existing suite that has nothing to do
  with a plain file-tree diff.
- **Engineer input/output:** built all four subagents and three skills,
  the `.agents/`→`.claude/` sync target and drift-check script, the new
  CI job, and the documentation index — then hit a real constraint
  attempting Part 4's proof-of-use: its own harness has a fixed
  subagent/skill roster snapshotted at session start, so it couldn't
  directly invoke the project-local `implement-issue` skill or launch
  `qa-engineer` by name from inside itself. Rather than skip the
  requirement or fake a result, it disclosed the constraint plainly and
  worked around it by shelling out to the real, separately-installed
  `claude` CLI in fresh, zero-context subprocesses — the closest
  available approximation of "a fresh session actually invoking these by
  name" — and recorded the verbatim invocations and responses.
- **Review:** QA treated the engineer's workaround as something to verify
  rather than take on faith — it reproduced the exact same harness
  constraint in its own session first (confirming the limitation was
  real, not a convenient excuse), then independently re-ran both of the
  engineer's exact invocations from its own fresh subprocesses. One
  re-run hit the identical, obscure Git-Bash path-rewrite quirk
  (`/implement-issue` silently rewritten to a filesystem path) that the
  engineer's transcript had also hit — strong, hard-to-fabricate evidence
  that the skill genuinely loaded rather than the model improvising a
  plausible-sounding answer. QA also deliberately introduced a one-byte
  drift between the `.agents/` and `.claude/` trees to prove
  `scripts/check-agents-sync.sh` actually catches a regression instead of
  trivially passing, before reverting it.
- **Verification:** `make sync-agents` + `scripts/check-agents-sync.sh`
  clean (exit 0), confirmed to genuinely detect drift when deliberately
  introduced (exit 1, correct file named) by both passes; every skill's
  claimed grounding fact-checked against the real files it cites; the
  new CI job confirmed minimal and correctly excluded from the deploy
  gate; no symlinks anywhere; only the 20 files the issue's constraints
  allowed were touched. QA verdict: PASS. Orchestrator closed issue #18
  and pushed `8d69e70` to `main`.

## 2026-10-14 — Issue #19: Pinpoint MCP server

- **Tool:** Claude Code, orchestrator + PM + Engineer + QA, each a fresh
  subagent per `_docs/process.md`. The repository owner's brief arrived as
  a single paragraph with no issue behind it, so the orchestrator first
  created #19 with that text as the raw scope and left all shaping to the
  PM.
- **PM input/output:** grounded the brief against the real code before
  writing criteria, and resolved the places where it did not match the
  API. There is no approve-status endpoint, so `approve_status` is derived
  from `status`/`approvedAt`/`approvedBy` on `GET /rooms/{id}` with no
  contract change. "Read-only" collides with email/password login, so the
  GET-only test allows exactly one exception, `POST /auth/login`, which
  creates a session and no data. `guestToken` in the `/rooms` payload lets
  its holder act as the client, so no tool may emit it. Studio tokens last
  60 minutes, so a single re-login on a self-caused 401 was added. Port
  8100 was confirmed for Compose, with a note that `make run` listens on
  8091 and `openapi.yaml`'s first server says 8000. Decided the `mcp` CI
  job stays out of `deploy.needs`, following the `agents-sync` precedent
  from #18 (the Dockerfile ships none of `mcp-server/`). Wrote the
  live-demo criterion so it cannot be satisfied by invention: a verbatim
  transcript, or a marked TODO and a QA FAIL. Side effects, not part of
  the brief: it filed #20 (`GET /health` is missing from `openapi.yaml`)
  and #21 (run the MCP integration test in the CI stack job), and added
  two rows to the gitignored `_local/make-it-better.md`. I reviewed the
  extra issues as out-of-scope follow-ups, not as scope creep in #19.
- **Engineer input/output:** built `mcp-server/` (client with auth and
  error mapping, five `readOnlyHint` tools, 51 respx-mocked tests plus a
  stdio protocol test and a 6-test integration module skipped unless
  `PINPOINT_BASE_URL` is set), `.mcp.json`, `make mcp-test`, the `mcp` CI
  job, and the docs, in five commits. Rejected an unpinned `mcp`: `uv add`
  resolved 2.3.0, which renamed FastMCP, so it pinned `>=1.12,<2` (locked
  1.30.0) and explained why in the commit and README. One of its own tests
  caught a real leak, the client dataclass `repr` included the password
  and token, fixed with `repr=False`. It captured the demo transcript from
  a real headless `claude -p` session against `make up`, needing
  `--settings enabledMcpjsonServers` because the project server was
  pending approval, and rendered it with a script that only lays events
  out. It noticed it had briefly passed the demo password as a redaction
  pattern, which also redacted the server name, and re-rendered. It did
  not push, so the throwaway-red CI criterion was left unverified.
- **Review:** QA re-ran everything from fresh clones rather than trusting
  the engineer, and re-ran the demo question itself in a new headless
  session, getting the same tool-call sequence and the same answer
  (Lakeside 1, Atrium 0). It checked the two pasted transcripts are
  byte-identical and read the render script for rewriting. It exercised the
  server through a real MCP stdio client and with a closed port. It also
  confirmed no forbidden file changed and that all commits carry no
  trailers. It declined to push to prove the CI criterion, since a push
  to `main` deploys to production and nobody had authorised that, and
  instead showed a deliberately broken test fails the job's exact
  commands, then reverted it. It marked that line "verified locally only".
  Non-blocking finding: `server.py` imports `pydantic` without declaring
  it, which only works transitively through `mcp`.
- **Verification:** `make mcp-test` 51 passed / 6 skipped; the integration
  module against `make up` 6 passed; `make test` 86, `make frontend-test`
  51, `make integration` 14 + 1, `make e2e` 2, agents-sync clean. QA
  verdict: PASS, with one gap stated openly: the CI `mcp` job has not run
  on GitHub. Orchestrator closed #19 on that basis. It did not push; the
  five commits are on local `main` only, and the first push or a PR should
  confirm the job.

## 2026-10-14 — Issue #22: Agent hooks, guardrails and permission notes

- **Tool:** Claude Code, orchestrator + PM + Engineer + QA, each a fresh
  subagent per `_docs/process.md`. The repository owner's brief arrived as
  a four-part paragraph with no issue behind it, so the orchestrator created
  #22 with that text as the raw scope plus a list of repo facts it had
  checked (where `on-call-responder` lives, what the "issue #12 incident
  log" is, the secret names in `ci.yml`, which interpreters exist on the
  development machine), and left all shaping to the PM.
- **PM input/output:** read the brief against the repo and settled the
  places where it was underspecified or collided with existing rules. The
  hook runs through a POSIX `sh` launcher that probes `python3` then
  `python`, so the Windows Store `python3` stub is skipped; it is
  stdlib-only and never uses `uv`. No interpreter found is fail-open with
  a loud stderr warning, with the rationale (fail-closed would block the
  Bash command needed to repair the hook) to be written down. `custom-agent/`
  references `on-call-responder` instead of moving it, because Claude Code
  loads only `.claude/agents/` and the `agents-sync` CI job requires both
  trees to match. The example run must use the real #12 reopening comment
  (Render exit 127) and be compared honestly with the later Engineer/QA
  correction of its root cause. The live check of the hook may only run
  when local `main` equals `origin/main`, so a hook that failed to fire
  would make `git push --force origin main` a no-op, and its output goes to
  a file that is read before anything is pasted. Surfaced rather than
  silently resolved: the `_local/` block collides with the PM's
  parking-lot flow (documented as a narrow Edit/Write exception), the
  PowerShell tool is not covered by a `Bash` matcher (documented as a gap),
  "close issues" is narrowed to the orchestrator after QA PASS to match
  `process.md`, and `rm -rf` in `/tmp` is blocked as scoped. Two ideas were
  parked in the gitignored `_local/make-it-better.md`. The orchestrator
  reviewed these as in-scope groomings and kept the owner's scope of
  "Bash commands" rather than widening the matcher.
- **Engineer input/output:** was given the groomed issue and the
  orchestrator's clarification that the live hook check runs in a throwaway
  clone with a local bare `origin` and a dummy env file, because local
  `main` cannot equal `origin/main` once the hook is committed. Built
  `agent-hooks/`: a stdlib-only `pretool_bash_guard.py` with five rules, a
  `posttool_test_reminder.py`, and a POSIX `run.sh` launcher. Wired both in
  `.claude/settings.json` with `hooks` placed before `attribution`, so the
  attribution line is byte-identical and the diff is additions only. Added
  `make hooks-test` and a CI `hooks` job kept out of `stack.needs` and
  `deploy.needs`. Wrote 52 `unittest` tests that call the scripts as
  subprocesses with stdin JSON. Wrote `agent-hooks/README.md`,
  `docs/permissions.md`, three rows in the extension-pack table and
  `custom-agent/README.md` with a real `on-call-responder` run on the
  verbatim #12 reopening comment. Four commits, two issue comments (live
  evidence, implementation summary), nothing pushed.
- **Review:** rejected a fail-closed launcher, since a missing Python
  would block the Bash command needed to repair the hook. Rejected moving
  `on-call-responder` into `custom-agent/`, which would break loading and
  the `agents-sync` job. Rejected recursing into `bash -c` and `eval`
  strings because the issue lists them as documented gaps and the docs
  would otherwise overclaim. Kept heredoc bodies and quoted text as data so
  commit messages that mention a blocked pattern are not blocked. Made the
  env-file rule deny by default with a short non-printing allowlist rather
  than a list of verbs, which also means `cp .env.example .env` is denied
  in an agent's shell; the Engineer hit this itself and used the
  PowerShell tool for the dummy file. It did not fix stale lines 26 and 43
  of `docs/deployment.md` (they still describe the removed
  `dockerCommand`, found by the `on-call-responder` run) because that file
  is outside the issue's file list. It did not present the example run as
  an independent diagnosis: the agent read `render.yaml` and this report,
  which already held the corrected cause, and said so.
- **QA input/output (first pass: FAIL):** a fresh QA session checked
  criteria A to G against the committed files and by running them. It piped
  about 300 PreToolUse payloads into the launcher (every listed deny and
  allow spelling, extra bypass spellings, unterminated quotes, heredocs and
  commit messages that mention a blocked pattern, malformed input, ordinary
  git, make, docker, pytest and gh commands), checked the PostToolUse
  reminder on `backend/`, `frontend\` and absolute Windows paths, compared
  the live-evidence block messages with the guard's real output, and
  scanned every changed file for values from the real local env file
  without printing any. It posted `## QA: FAIL` on criterion G only: a
  stray blank line in `docs/agent-extension-pack.md` ended the Markdown
  table, so the hook, permissions and custom-agent rows rendered as plain
  pipe text. No test covers that file, so only a look at the rendered
  structure could catch it. QA also recorded non-failing friction: the
  env-file rule is deny-by-default and blocks some harmless commands that
  only name the file as a search pattern (`grep -rn ".env" docs`,
  `find -name ".env*"`), and `docs/deployment.md` lines 26 and 43 are stale.
- **Engineer fix pass:** a fresh Engineer got QA's comment as its only
  input and deleted that single blank line (commit `31047a5`, one deletion
  in one file), checked every line of the table starts with `|`, and
  reran `make hooks-test` and the sync check. The non-failing observations
  were deliberately left alone.
- **QA input/output (second pass: PASS):** another fresh QA session
  re-checked G on the file (rows contiguous, all six criterion-12 items
  point at existing paths), reran `make hooks-test` (52 tests, OK),
  `check-agents-sync.sh` (exit 0) and the `ci.yml` parse (`hooks` in
  neither `stack.needs` nor `deploy.needs`), spot-probed the guard with 65
  payloads that all matched, and confirmed the diff against `0a382f7`
  touches only the 15 whitelisted files with no trailers on any commit. It
  posted `## QA: PASS`. The orchestrator then closed the issue.
- **Review:** the orchestrator accepted the PM's defaults rather than
  widening scope: the hook matcher stays `Bash` as the owner wrote
  (the PowerShell tool is a documented gap), "close issues" follows
  `process.md` (orchestrator after QA PASS), and the `_local/` block has a
  narrow documented exception for the PM's parking-lot file. It changed one
  thing the PM had put in the Engineer's hands: the live force-push check
  runs in a throwaway clone, because a committed hook means local `main`
  can no longer equal `origin/main`, and a hook that failed to fire there
  could neither touch GitHub nor leak a real secret.
- **Verification:** `make hooks-test` passes (52 tests, Windows, Git Bash,
  Python 3.14, no `uv`) in both QA passes and in the Engineer's runs. A
  fresh headless Claude Code session in the throwaway clone had
  `git push --force origin main` and `cat .env` blocked by the guard's own
  rule messages (hook exit 2) while the control `cat .env.example` ran; the
  evidence is in the issue thread. The PostToolUse reminder reached the
  agent after a `Write` under `backend/`. The launcher printed its
  "guardrails are NOT active" warning and exited 1 with no Python on
  `PATH`. A real `on-call-responder` run on the verbatim #12 reopening
  comment made 12 tool calls, all Read, Glob and Grep. **Not verified:**
  the `hooks` CI job on GitHub (checked after the push, see below), Linux
  and Python 3.8 to 3.13 locally, other assistants' hook formats (marked
  "not verified" in `agent-hooks/README.md`), and the backend, frontend,
  MCP, integration and e2e suites, which were not run because nothing under
  `backend/`, `frontend/` or `mcp-server/` changed and `uv` is not on this
  machine's PATH. **Follow-ups:** `docs/deployment.md` lines 26 and 43
  still describe the removed `dockerCommand`; the env-file rule's false
  positives may need loosening if they get in the way.
- **After the push:** CI run 38615036442 on `ac7c85a` was green, including
  the new `hooks` job on Linux (so the guard and its 52 tests pass on a
  non-Windows interpreter) and `deploy`. This closes the "hooks job not seen
  green" gap above. Python 3.8 to 3.13 and a local Linux run remain
  unchecked.

## 2026-10-14 — Issue #23: Loosen the .env guard: allow .env.example and mentions of .env

- **Tool:** Claude Code, orchestrator + PM + Engineer + QA, each a fresh
  subagent per `_docs/process.md`. The owner's follow-up brief to #22 had no
  issue behind it, so the orchestrator created #23 with that text as raw
  scope and left the shaping to the PM.
- **PM input/output:** read the guard, its tests, the hooks README,
  `docs/permissions.md` and the QA and Engineer comments on #22, and
  rewrote the issue around the seven real false positives (`grep -rn ".env"
  docs`, `ls -a | grep -E '^\.env'`, `find . -name ".env*"`, `cp
  .env.example .env.example.bak`, `cat .env.example.bak`, a quoted `.env`
  word in a `for` loop, and `cp .env.example .env`). Decided that a `cp`
  from a template onto exactly `.env` is the only permitted write to `.env`
  (`cat .env.example > .env`, `mv`, `tee`, `sed -i` and `cp .env .env.bak`
  stay denied), how template names and backup suffixes are recognised, and
  that grep patterns, `find -name` patterns, `for` word lists and `echo`
  operands are harmless mentions while `find -exec`, `grep -f .env` and
  `--include=".env*"` stay denied. The one existing deny case that flips on
  purpose is named. Required a row in `_docs/decisions.md` (the #22 spec
  said to deny `cp` into `.env`, and a later session would re-implement
  that from `docs/` alone), the `docs/permissions.md` and README wording,
  and `make hooks-test` without `uv`. Parked a no-clobber check and
  readers that do not name the file in `_local/make-it-better.md`. The
  orchestrator reviewed the open questions and kept the PM's defaults: the
  silent overwrite of an existing `.env` by the owner's own README command
  is accepted and documented, because the owner said that exact command must
  pass, and the `_docs/decisions.md` row is covered by the owner's
  correction, which `AGENTS.md` says to record in `_docs/`.
