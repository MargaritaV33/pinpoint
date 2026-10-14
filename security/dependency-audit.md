# Dependency audit

Issue #26, rubric criterion 13. Date: 2026-10-14. Audited commit:
`586936d85bdd116b50a6cbef1427cfbeebd976be` (`backend/uv.lock` and
`frontend/package-lock.json` were last changed in
`f54c15d42799fc4b226c50f62246668a8a8582d8`; no later commit touches them).
One-off and manual: running these on a schedule in CI is #29.

Result: **no known vulnerability in either stack, runtime or dev.** An empty
table is a result, not a gap; the inventories below say what was looked at.
"No advisory" means none was published in the advisory source on the audit
date; it does not mean none will be.

## Backend (Python): pip-audit

- Tool: `pip-audit 2.10.1`, installed with `pip install pip-audit` into a
  throwaway virtual environment **outside the repository** (`python -m venv`
  in a scratch directory, Python 3.12). It is not a dependency of the project:
  nothing changed in `backend/pyproject.toml` or `backend/uv.lock`. Re-run with
  `pip install pip-audit==2.10.1` to reproduce.
- Why not `uv`: it is not on this machine. The lock file is plain TOML, so
  [`lock_to_requirements.py`](lock_to_requirements.py) (standard library only)
  reads `backend/uv.lock` and prints `name==version` for every package
  reachable from the project's non-dev dependencies, extras followed. That is
  the set `uv sync --frozen --no-dev` installs in the `Dockerfile`.
  Environment markers are ignored on purpose, so the set is a superset of what
  any one platform installs.
- **What was done: the runtime closure** (29 packages), then, as a second run,
  the whole lock (38 packages: the 29 plus 9 dev-only: `certifi`, `colorama`,
  `httpcore`, `httpx`, `iniconfig`, `packaging`, `pluggy`, `pygments`,
  `pytest`).

```bash
python -I security/lock_to_requirements.py > reqs-runtime.txt          # 29 lines
python -I security/lock_to_requirements.py --all | sed 's/  # dev-only//' > reqs-all.txt   # 38 lines
pip-audit -r reqs-runtime.txt --no-deps --disable-pip
pip-audit -r reqs-all.txt     --no-deps --disable-pip
```

Both runs printed `No known vulnerabilities found` (exit code 0). pip-audit
warned that `--no-deps` is better used with hashed requirements; the lock file
pins hashes, but the generated file does not carry them, so the tool resolved
by name and version only.

Runtime inventory audited: annotated-doc 0.0.5, annotated-types 0.8.0, anyio
4.15.1, bcrypt 4.0.1, click 8.5.0, fastapi 0.143.0, h11 0.16.0, httptools
0.9.0, idna 3.20, opentelemetry-api 1.45.1, passlib 1.7.4, psycopg 3.3.6,
psycopg-binary 3.3.6, pydantic 2.14.1, pydantic-core 2.50.1, pydantic-settings
2.15.0, pyjwt 2.15.1, python-dotenv 1.2.4, python-multipart 0.0.32, pyyaml
6.0.3, sqlalchemy 2.1.4, starlette 1.7.0, typing-extensions 4.16.0,
typing-inspection 0.4.4, tzdata 2026.5, uvicorn 0.54.0, uvloop 0.23.0,
watchfiles 1.3.0, websockets 17.2.

| Package | Installed | Advisory id | Severity (source) | Fixed in | Disposition |
|---|---|---|---|---|---|
| none | | | | | no advisory for any of the 38 locked packages |

pip-audit does not report severity. There were no advisories, so no severity
had to be taken from a GHSA/OSV record and none is guessed here.

One note that is not an advisory: `bcrypt` is pinned `<4.1` in
`backend/pyproject.toml` (locked 4.0.1) because bcrypt 5.0 broke `passlib` 1.7.4's
import-time self-test (`docs/ai-usage-report.md`, entry for issue #4; commit
`220f89a`). It has no advisory today; the pin is
discussed in [`pr-audit.md`](pr-audit.md).

## Frontend (npm): npm audit

- Tool: `npm 11.6.2` (Node v24.13.0) in `frontend/`, against the committed
  `package-lock.json`. No `npm install`, no `npm audit fix`; `git status` shows
  `frontend/package-lock.json` unchanged.
- Production dependencies: `npm audit --omit=dev` found **0 vulnerabilities**
  (info 0, low 0, moderate 0, high 0, critical 0; 254 production packages in
  the dependency tree).
- Informational, build-time only: `npm audit` with dev dependencies included
  (581 packages in total, of which 270 dev-only) also found **0
  vulnerabilities**. Dev dependencies run on a developer machine or in CI, never
  in the deployed image's server process.

| Package | Installed | Advisory id | Severity (source) | Fixed in | Disposition |
|---|---|---|---|---|---|
| none | | | | | no advisory in the npm registry's audit endpoint |

## Limits

- Advisory databases are queried live (PyPI/OSV for pip-audit, the npm registry
  for npm audit); the result is true for 2026-10-14 only.
- Neither tool sees system packages in the base images (`python:3.12-slim`,
  `node`, `postgres:16-alpine`), nor the Docker images themselves.
- `mcp-server/` and `integration/` have their own `uv.lock` files and were not
  audited here (the task names the backend and the frontend).
- Supply-chain hardening such as a dependency cooldown for `uv` is reported by
  Semgrep (F18, F19 in [`semgrep-report.md`](semgrep-report.md)), not by these
  audits.
