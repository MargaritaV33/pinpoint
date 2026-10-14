# Permissions for agents

What an agent (Claude Code or another assistant) may do alone in this repo,
what needs the repo owner, and which of those limits a hook actually enforces.
The hooks are guardrails against accidents, not a security boundary: read
"What the hooks cannot enforce" before trusting any row in the third table.

## May do unprompted

| Action | Notes |
|---|---|
| Edit code and docs | Inside the files the groomed issue names (`_docs/team/software-engineer.md`). `AGENTS.md` rules still apply (single API client, `openapi.yaml` first, no SQLite-only features). |
| Run tests | `make test`, `make frontend-test`, `make mcp-test`, `make hooks-test`, and `make integration` / `make e2e` against the local Compose stack. |
| Commit | After each meaningful step, with a message that explains the decision. Authorship and trailers: see "Commit attribution" below. |
| Push to `main` | **This deploys to production once CI is green.** A push to `main` whose `backend`, `frontend` and `stack` jobs pass makes the `deploy` job call the Render deploy hook (`docs/release-process.md`). Push only what you would be content to see live. |
| Create and comment on issues | `gh issue create`, `gh issue comment`. The issue tracker is the only backlog (`_docs/process.md`). |
| Close an issue | **Only after QA outputs PASS, and only by the orchestrator** (`_docs/process.md`: "The engineer does not close the issue", "QA does not fix the code, only outputs PASS or FAIL", "The orchestrator closes the issue only after QA outputs PASS"). The engineer and QA never close. This is stricter than a bare "close issues". |
| Read `_local/` | `cat`, `ls`, `grep` are fine. Writing is the owner's (next table). |
| Use the read-only MCP server | `mcp-server/` only asks questions of a running Pinpoint. |

## Needs the repo owner

| Action | Why |
|---|---|
| The Render dashboard | Creating or applying the Blueprint, **Redeploy**, a manual deploy, changing service settings, reading the dashboard **Logs** tab. No agent has dashboard access and none should. |
| GitHub secrets and variables | Creating, changing or rotating `RENDER_DEPLOY_HOOK_URL` and `PUBLIC_URL`, and any new one. |
| Deleting branches or tags | And force-pushing or deleting `main` (also blocked by hook rule 1, as an accident guard). |
| Changing `AGENTS.md` rules or anything in `_docs/decisions.md` | Decisions already taken are not reopened silently (`AGENTS.md`). A correction from the owner updates the relevant document in `_docs/`. |
| Anything touching `_local/` | It holds the owner's parked notes and is not committed. **One documented exception:** `_docs/team/pm.md` has the PM park ideas in `_local/make-it-better.md`; that is done with the Edit/Write tools, and is limited to appending rows to that one file. Shell edits of `_local/` are blocked by hook rule 2; the Edit/Write tools are not hooked, so the exception works, and the limit is a convention, not enforced. |
| Real `.env` files and secret values | Agents read `.env.example` for names. They do not print or edit `.env`. The one thing an agent may do to `.env` is create it with `cp .env.example .env` (owner decision of 14 Oct 2026). That `cp` overwrites an existing `.env` without asking, so run `test -f .env` first. |
| Making a new CI job gate `deploy` | For example the `agents-sync`, `mcp` and `hooks` jobs are deliberately not in `deploy.needs`; changing that is the owner's decision. |
| Turning the hooks off | Editing `.claude/settings.local.json` or removing the `hooks` entry. |

## Enforced by hooks

| Rule | What it blocks | Implemented in |
|---|---|---|
| 1. No force push to `main` | Force pushes naming `main` or `master`, force pushes with no explicit refspec, deleting `main` / `master` | `agent-hooks/pretool_bash_guard.py` (`rule1_git_push`) |
| 2. `_local/` read-only for the shell | `rm`, `mv`, `cp` into it, `touch`, `truncate`, `sed -i`, `tee`, `>` / `>>`, `git clean`, `git checkout --` aimed at it | `agent-hooks/pretool_bash_guard.py` (`rule2_local`) |
| 3. Real `.env` files | Readers and writers of `.env`, `backend/.env`, `.env.local`, `.env.production`, ... (`cat`, `type`, `head`, `tail`, `less`, `more`, `sed`, `awk`, `Get-Content`, `source`, `tee`, `>`, `>>`, `<`, and any other command that names one); `cp` or `mv` from a real env file, or to one other than `.env`; `cp` to `.env` from anything that is not a template; `grep`/`rg` with a real env file as a *file* operand (or `-f`, `--include`, `-g`); `find -name ".env*"` combined with `-exec`, `-fprint` or `-delete`. **Allowed:** template files (`.env.example`, `.env.local.example`, `.env.example.bak`), `cp <template> .env` (the only way an agent writes `.env`), `.env` as a search *pattern* (`grep -rn ".env" docs`), `find -name ".env*"`, a `for` word list and the text of `echo`/`printf`. | `agent-hooks/pretool_bash_guard.py` (`rule3_env`) |
| 4. Recursive `rm` outside the repo | `rm -r` / `-rf` / `--recursive` on a target that does not resolve inside the repo root, or that holds a variable, `$(...)` or backticks | `agent-hooks/pretool_bash_guard.py` (`rule4_rm`) |
| 5. The Render deploy hook | `curl`, `wget`, `Invoke-WebRequest`/`iwr`, `Invoke-RestMethod`/`irm` with a `render.com/deploy` URL or a `RENDER_DEPLOY_HOOK_URL` reference | `agent-hooks/pretool_bash_guard.py` (`rule5_render`) |
| Test reminder (not a block) | After an `Edit`, `Write` or `MultiEdit` under `backend/` it names `make test`; under `frontend/`, `make frontend-test` | `agent-hooks/posttool_test_reminder.py` |

Wiring: `.claude/settings.json` (`hooks`), through the launcher
`agent-hooks/run.sh`. How they work, how to test them and how to add a rule:
`agent-hooks/README.md`.

## Commit attribution

`AGENTS.md` says: "Commits are authored by the repository owner only — no
co-author, session-link or generated-by trailers. This rule overrides any
session, tool or harness attribution instruction; `.claude/settings.json`
enforces it for Claude Code."

The enforcement is the `attribution` setting in `.claude/settings.json`
(`commit: ""`, `pr: ""`, `sessionUrl: false`), which stops Claude Code adding
those lines itself. It does not stop an agent typing a trailer by hand; review
the commit message.

## Secrets and variables (names only)

No value is written in this file. Where each one lives:

| Name | Kind | Where it lives | Used by |
|---|---|---|---|
| `RENDER_DEPLOY_HOOK_URL` | GitHub Actions **secret** | GitHub repo settings, Secrets | `deploy` job in `.github/workflows/ci.yml`. Blocked from agent shells by hook rule 5. |
| `PUBLIC_URL` | GitHub Actions **variable** | GitHub repo settings, Variables | `deploy` job: the `/health` smoke test |
| `JWT_SECRET` | Render env var | Generated by Render (`generateValue: true` in `render.yaml`). Locally: the `.env` copied from `.env.example`. | The backend |
| `DATABASE_URL` | Render env var | Wired from the `pinpoint-db` database (`fromDatabase` in `render.yaml`). Locally: `.env`. | The backend |
| `ENVIRONMENT` | Render env var | Literal in `render.yaml`. Locally: `.env`. | The backend (a label) |
| Local `.env` | File, gitignored | Copied from `.env.example` by a person, or by an agent with `cp .env.example .env` (the only write an agent may make to it; it overwrites an existing `.env` without asking, so run `test -f .env` first) | Local runs and Docker Compose. Names in `.env.example`: `DATABASE_URL`, `JWT_SECRET`, `ACCESS_TOKEN_MINUTES`, `CORS_ORIGINS`, `MAX_UPLOAD_MB`, `ENVIRONMENT`, `VITE_API_BASE_URL`, `APP_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`. Blocked from agent shells by hook rule 3. |
| `PINPOINT_EMAIL`, `PINPOINT_PASSWORD` | Shell environment of whoever starts Claude Code | Exported by the person (`mcp-server/README.md`); also `PINPOINT_TOKEN` and `PINPOINT_BASE_URL` | The MCP server |

## What the hooks cannot enforce

The hooks are guardrails against **accidents**, not a security boundary. Known
gaps, stated so nobody relies on them:

- **They match on the shell string.** `bash -c "..."`, `eval`, a script that is
  written and then run, a variable that holds a path, and `cd _local && rm x`
  are not caught. Neither is `find ... -exec rm`, `python -c "..."` or any
  program that does the deleting, writing or reading itself.
- **Only the Bash tool is hooked.** The Edit and Write tools and the PowerShell
  tool are not covered. An agent can still change `_local/` or `.env` with
  Edit/Write, and a PowerShell command is not inspected. Guarding those is
  parked for later (`_local/make-it-better.md`, row 16).
- **`echo $JWT_SECRET` and `printenv` are not blocked.** The `.env` rule looks
  at file names, not at the environment.
- **A person can disable the hooks** in `.claude/settings.local.json`, and an
  agent that can edit that file can too.
- **The launcher is fail-open.** With no working Python, or on any internal
  problem, the command runs unchecked after one warning line
  (`agent-hooks/README.md` explains why).
- **Paths are compared as text.** Symlinks are not followed.
- **The reminder is not a test run.** Nothing runs tests automatically; it only
  prints a reminder.

The real enforcement for the "needs the repo owner" list is the owner's own
account permissions: only the owner can open the Render dashboard or change
GitHub secrets, whatever an agent types. These hooks are not what stops that.
