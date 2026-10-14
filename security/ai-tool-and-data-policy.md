# AI tool and data policy

Issue #26, rubric criterion 13. Review date: **2026-10-14**. Owner: the
repository owner. This policy describes what the repository shows and what
enforces it. Where nothing enforces a rule, the rule says "not enforced". It
does not say a control exists unless a file, a CI job or a setting that can be
checked is named.

Premise: anything an AI tool reads in a session is processed by that tool's
provider. That is why the data tiers below exist.

## Tools

Only tools the repository shows. Each line names its source file.

| Tool | Used for | Source |
|---|---|---|
| Claude Code, as an orchestrator that launches PM, Software Engineer and QA Engineer subagents | Building and verifying nearly all of Pinpoint, one fresh session per role and step | `docs/ai-usage-report.md:9-12` (Summary); roles in `.claude/agents/*.md`, `_docs/process.md` |
| Model `claude-sonnet-5-5` | The recorded live MCP demo run. Other sessions' models are not recorded in the repository. | `mcp-server/README.md`, "Live demo transcript" |
| Lovable | First prototype of the frontend (issue #2), imported from a private repository, then adapted. It used a mocked service layer. Lovable's error-reporting telemetry was stripped from the code in `ef27737`. | `docs/ai-usage-report.md:13-14,155-160`; `git show ef27737` |
| The local `pinpoint` MCP server | Read-only questions about a running Pinpoint (five tools), over stdio, started by Claude Code | `.mcp.json`; `mcp-server/README.md` |
| Semgrep (Docker image `semgrep/semgrep:1.180.0`, locally and in the CI `security` job) | Static scan of a read-only export of the tracked files, metrics off; not an AI tool but a third-party container that sees repository files | `security/semgrep-report.md`; `.github/workflows/ci.yml` (`security`) |
| `pip-audit` and `npm audit` | One-off dependency audits; they send package names and versions to the advisory services | `security/dependency-audit.md` |

Other assistants (Codex, Cursor, Gemini CLI, Claude Desktop, VS Code clients):
**not used, not verified** here. The hook guard and the MCP server configs are
documented for them but were not run (`agent-hooks/README.md`, "Using it from
another assistant"; `mcp-server/README.md`, "Other assistants"). No other tool
is part of this policy; adding one means adding a line above first.

## Data tiers

| Tier | What | Source | How it is enforced today |
|---|---|---|---|
| **May see** | Source code, issues and comments, `docs/`, `_docs/`, the seed images in `backend/app/seed_images/` (demo renders, copied from the frontend prototype, see `docs/ai-usage-report.md`, issue #6 entry), `.env.example` | `docs/permissions.md:12-19` (what an agent may do unprompted); `AGENTS.md` | Not restricted: this is the content of the public repository. Hook rule 3 explicitly allows `.env.example` (`agent-hooks/README.md`, "The rules"). |
| **May see locally, must not leave the machine or enter a public file** | `_local/` (the owner's parked notes) | `docs/permissions.md:18` (agents may read it with `cat`, `ls`, `grep`) and `:29` (writing is the owner's, one documented exception for the PM); `_docs/team/pm.md:18` | `_local/` is in `.gitignore:28`, so it is not committed. Hook rule 2 blocks **shell** writes to it. Reading is allowed. The Edit and Write tools are not hooked, so the PM's append works and the "append only" limit is a convention, **not enforced**. It is not excluded from the Docker build context (`.dockerignore` lacks it; tracked in #37), and nothing checks that its contents do not end up in an issue or a public file. The Semgrep scan never mounts it (it scans an export of tracked files). |
| **Must not see** | The real `.env`; the production database; the Render dashboard and logs; GitHub secrets and variables; real client renders and real client names | `docs/permissions.md:25-26,30`; `docs/permissions.md`, "Secrets and variables" | See the table below. In short: the `.env` rule covers the Bash tool only; no agent has Render or database credentials; nothing checks an upload for real client material. |

How each "must not see" item is protected, row by row:

| Item | Enforced by | Not enforced |
|---|---|---|
| Real `.env` | Hook rule 3 blocks shell readers and writers of `.env` and variants, and allows `cp .env.example .env` (`docs/permissions.md:40`) | Rule 3 matches Bash commands only. The `Read`, `Edit`, `Write` and PowerShell tools are not hooked; `printenv` and `echo $VAR` are not blocked; `grep -r` and `git grep` can reach a real `.env` without naming it (`agent-hooks/README.md`, "What the hooks cannot enforce"). `cp .env.example .env` overwrites an existing `.env` (`docs/permissions.md:30`). |
| Production database | `DATABASE_URL` for production is wired by Render from the managed database (`render.yaml`); `docs/permissions.md:25` says no agent has dashboard access | No technical control inside the repository stops a person from putting a production URL in a local environment. |
| Render dashboard and logs | Only the owner's own account permissions (`docs/permissions.md:25`, "Needs the repo owner"; closing paragraph of that file) | Not a hook: the hooks are not what stops this. |
| GitHub secrets | The secret values live in GitHub and are not in the repository (`docs/permissions.md`, "Secrets and variables"); hook rule 5 blocks shell commands naming `RENDER_DEPLOY_HOOK_URL` or the deploy URL (`docs/permissions.md:42`) | Rule 5 matches Bash commands only. |
| Real client renders and client names | Nothing | **Not enforced.** The upload route checks the claimed file type and size (`backend/app/routers/images.py`), not who owns the picture, and no job scans uploads or the repository for client material. The production database is not visible to agents, but anything a person uploads there is the owner's responsibility. The demo data is documented as demo (`pr-audit.md`, A-16). |

## The `_local/` conflict

The brief for this issue says AI tools never see `_local/`. The repository says
otherwise: `docs/permissions.md:18` lets an agent read it (`cat`, `ls`, `grep`)
and `docs/permissions.md:29` plus `_docs/team/pm.md:18` have the PM append ideas
to `_local/make-it-better.md` with the Edit/Write tools.

**Current rule, as the repository operates today:** agents may read `_local/`
locally; its contents are never committed, never mounted into a third-party
tool such as the Semgrep container, and never pasted into issues, pull requests
or public documents. Only the first of those is partly technical (`.gitignore`);
the rest are conventions that nothing checks. **Owner to confirm or tighten.**
Tightening it (for example "no agent reads `_local/` at all") means changing
`docs/permissions.md` and the PM role, which this policy does not do. This is
open question 1 of issue #26; the default above was used.

## Review before merge

The rule: **QA agent plus human review before deploy-affecting changes.** It is
**not enforced today**:

- There is no pull-request flow: all work is pushed straight to `main`.
- `docs/permissions.md:15` lets an agent push to `main` unprompted.
- A push to `main` whose `backend`, `frontend` and `stack` jobs pass deploys
  to production (`.github/workflows/ci.yml`, job `deploy`, `needs: [stack]`).
- `main` is not protected: `gh api repos/MargaritaV33/pinpoint/branches/main/protection`
  answers HTTP 404, "Branch not protected" (checked 2026-10-14).
- There is no CODEOWNERS file.

What **is** enforced: the QA gate of `_docs/process.md` ("The orchestrator closes
the issue only after QA outputs PASS"), which is a convention carried out by the
orchestrator and not a technical control; hook rule 1 (no force push to `main`,
`agent-hooks/pretool_bash_guard.py`); and CI gating of the `deploy` job on the
`stack` job. The new `security` job is deliberately not in `deploy.needs`:
whether it should be is #27. Branch protection, required checks, required
reviews and CODEOWNERS are owner-only GitHub settings: #28. Agent definitions
and the MCP credential: #36.

## Attribution

Commits are authored by the repository owner only: no co-author, session-link or
generated-by trailers (`AGENTS.md:34`). For Claude Code this is enforced by the
`attribution` setting in `.claude/settings.json` (`commit: ""`, `pr: ""`,
`sessionUrl: false`). It is **not enforced** against a trailer typed by hand
(`docs/permissions.md`, "Commit attribution"). AI use is not hidden: it is
disclosed in `docs/ai-usage-report.md`, where every step appends an entry
(`_docs/process.md`, "AI usage log"). So the commit history stays clean and the
disclosure lives in the report.

## How this policy is kept

- **Who updates it:** the repository owner. An agent proposes changes through an
  issue; it does not edit this file to widen what agents may see.
- **Where it is linked from:** the documentation list in `README.md` (one line)
  and `docs/agent-extension-pack.md` (one line).
- **Review date:** 2026-10-14. No next date is scheduled and nothing reminds the
  owner; the policy is out of date the first time a tool, a data tier or a
  control above changes without an edit here.
- **Related, not duplicated here:** [`agent-extension-security.md`](agent-extension-security.md)
  (risks of the agent extensions), [`pr-audit.md`](pr-audit.md) (review of the
  auth, image and upload code), [`semgrep-report.md`](semgrep-report.md) and
  [`dependency-audit.md`](dependency-audit.md) (scans).
