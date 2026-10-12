# AI usage report

Running log of how AI tools were used to build Pinpoint. One entry per step:
what was asked, what came back, what was reviewed or rejected, how it was
verified. Consolidated into a narrative before submission.

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
