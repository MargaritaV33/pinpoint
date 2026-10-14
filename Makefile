.PHONY: sync run test frontend-test up down integration e2e sync-agents mcp-test

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

# Copies the canonical agent/skill definitions under .agents/ into the
# real (non-symlinked) working copy under .claude/ that Claude Code
# actually loads, removing anything on the .claude/ side that no longer
# exists on the .agents/ side. See agent-capabilities/README.md and
# scripts/check-agents-sync.sh.
sync-agents:
	rm -rf .claude/agents .claude/skills
	mkdir -p .claude/agents .claude/skills
	cp -r .agents/agents/. .claude/agents/
	cp -r .agents/skills/. .claude/skills/

# Unit tests of the read-only MCP server (mcp-server/). HTTP is mocked with
# respx: no backend or Docker needed. The integration test in the same folder
# is skipped unless PINPOINT_BASE_URL is set; see mcp-server/README.md.
mcp-test:
	cd mcp-server && uv run pytest
