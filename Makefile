.PHONY: sync run test frontend-test up down integration e2e

sync:
	cd backend && uv sync

run:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8091

test:
	cd backend && uv run pytest

frontend-test:
	cd frontend && npm install && npm test

up:
	docker compose up -d --build --wait

down:
	docker compose down -v

# Drives an already-running Compose stack (`make up`) over real HTTP. Does
# not start one itself — see docs/testing.md. Two invocations so the
# persistence test (which restarts the `app` container) only runs, and
# only once, after every independent scenario has already passed.
integration:
	cd integration && uv sync && uv run pytest tests/ --ignore=tests/test_persistence.py && uv run pytest tests/test_persistence.py

# Installs Chromium if needed, starts the Compose stack only if it isn't
# already running, runs the Playwright suite against it, and leaves the
# stack exactly as it found it. See e2e/scripts/run.mjs and
# docs/testing.md for the full detection/teardown contract.
e2e:
	cd e2e && npm install && node scripts/run.mjs
