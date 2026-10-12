# Backlog

Draft backlog from `product-spec.md`. Once moved to GitHub issues, the issues
are the only backlog and this file is archived under `_docs/outdated/`.

## 1. Repository skeleton with a passing test
Goal: An empty monorepo where `make test` and `make frontend-test` both pass.
Description: Create `backend/` (FastAPI app with `/health`, uv, pytest, one test) and `frontend/` placeholder structure, the `Makefile`, `.gitignore`, `.env.example`, and a README stub. No product code yet.

## 2. Frontend prototype with a mocked service layer
Goal: The whole client and studio UI runs in the browser against a mock API with seeded data.
Description: Generate the React + TypeScript app from the spec (Lovable), with every backend call centralized in `src/lib/api/` and a mock implementation behind the same interface. Screens: login/signup, rooms list, room (image switcher, pins, threads, export), guest page (name prompt, pins, approve). Add Vitest tests for the pin-coordinate math and the API client. Move the code into `frontend/`.

## 3. OpenAPI contract
Goal: `openapi.yaml` at the repository root describes every endpoint the frontend needs.
Description: Derive the contract from `frontend/src/lib/api/`: auth (signup, login, me), rooms (list, create, get, close), images (upload, list, get bytes, supersede), pins (list, create), comments (create), pin status (resolve/reopen), guest access (room by token, approve), export. Mark which endpoints need a bearer token and which accept a guest token.

## 4. Backend from the contract with an in-memory store
Goal: A FastAPI backend in `backend/` implements `openapi.yaml` against a seeded in-memory store, with tests.
Description: Modules `routers/`, `models.py`, `store.py`, `auth.py`. Hashed passwords and bearer tokens for studio endpoints; guest token for client endpoints; a `make run` target. Tests for every router.

## 5. Connect frontend and backend
Goal: The frontend talks to the real backend; the manual test scenario passes against the in-memory store.
Description: Switch the API client from mock to real, configure the base URL via env, fix CORS and any contract drift (update `openapi.yaml` first). Run `_docs/test-scenario.md` by hand.

## 6. Persistence with SQLAlchemy
Goal: Data survives a backend restart; SQLite by default, Postgres by `DATABASE_URL`.
Description: Replace the in-memory store with SQLAlchemy models (studio_user, room, image incl. bytes, pin, comment). Database-agnostic. Tests run on SQLite and, when a test DB URL is set, on Postgres.

## 7. Image upload and serving
Goal: JPG/PNG up to 15 MB can be uploaded, stored in the database and served back efficiently.
Description: Validate content type and size with clear errors; stream bytes on GET with cache headers; supersede endpoint. Tests for happy path and both rejections.

## 8. Dockerfile and Docker Compose
Goal: `docker compose up --build` runs the full system (app + Postgres) on one port.
Description: Two-stage Dockerfile (Node builds the frontend, Python image serves API and static files), `docker-compose.yaml` with healthcheck and volume, documented env vars.

## 9. Integration tests
Goal: `integration/` tests drive the compose stack over HTTP and cover the key workflows.
Description: Separate uv project, no backend imports. Scenarios: signup/login, room lifecycle, guest access and permissions, upload rejections, pin thread and resolve/reopen, approve, persistence after restart.

## 10. End-to-end test with Playwright
Goal: `make e2e` runs the manual test scenario in two browser contexts against the compose stack.
Description: `e2e/` project, studio context and guest context, asserts pins and replies appear and the room becomes approved.

## 11. CI pipeline
Goal: Every push and pull request runs backend tests, frontend tests, then the compose stack with integration and e2e tests.
Description: `.github/workflows/ci.yml` with backend and frontend jobs in parallel, a stack job that waits for both, logs and Playwright report uploaded on failure.

## 12. Deployment to Render
Goal: The app is reachable at a public HTTPS URL with a managed Postgres.
Description: `render.yaml` blueprint (web service from the Dockerfile + Postgres), env vars, `/health` check, first manual deploy. `docs/deployment.md`.

## 13. Continuous deployment
Goal: A green run on `main` deploys automatically and verifies `/health`.
Description: Deploy step in `ci.yml` using the Render deploy hook, gated on the stack job; post-deploy smoke test; `docs/release-process.md` with rollback.

## 14. Documentation pass
Goal: README, architecture, testing and AI-usage docs score full points on criteria 1, 2, 3, 14.
Description: README quick-start (run, test, compose, deploy), `docs/architecture.md` with a diagram and a technology table, `docs/testing.md`, `docs/ai-usage-report.md` consolidated from the running log.

## 15. Reproducibility check
Goal: A fresh clone on another machine runs, tests and composes from the README alone.
Description: QA agent follows the README from scratch, files every gap as an issue, fixes merged before submission.
