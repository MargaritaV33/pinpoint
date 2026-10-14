# Agent extension pack

Discoverable subagent and skill definitions for Claude Code (and the
course's cross-assistant convention), describing this project's own
already-documented process. See `agent-capabilities/README.md` for how
the canonical and working-copy trees stay in sync.

| Capability | Where it lives | How to invoke | What it's for |
|---|---|---|---|
| `pm` subagent | `.agents/agents/pm.md`, `.claude/agents/pm.md` | Launch the `pm` subagent by name | Grooms a GitHub issue per `_docs/team/pm.md` and `_docs/process.md` before anyone implements it |
| `software-engineer` subagent | `.agents/agents/software-engineer.md`, `.claude/agents/software-engineer.md` | Launch the `software-engineer` subagent by name | Implements one already-groomed issue per `_docs/team/software-engineer.md` and `_docs/process.md` |
| `qa-engineer` subagent | `.agents/agents/qa-engineer.md`, `.claude/agents/qa-engineer.md` | Launch the `qa-engineer` subagent by name | Verifies finished work against the issue's acceptance criteria and posts a PASS/FAIL verdict, per `_docs/team/qa-engineer.md` and `_docs/process.md` |
| `on-call-responder` subagent | `.agents/agents/on-call-responder.md`, `.claude/agents/on-call-responder.md` | Launch the `on-call-responder` subagent by name | Diagnoses a production symptom (`/health` shape, failed `deploy` job, Render 5xx) using `docs/deployment.md` and `docs/release-process.md` as its runbook, and proposes — never runs — the fix |
| `implement-issue` skill | `.agents/skills/implement-issue/SKILL.md`, `.claude/skills/implement-issue/SKILL.md` | Invoke the `implement-issue` skill (e.g. `/implement-issue`) | Walks one issue through the PM → Engineer → QA lifecycle from `_docs/process.md`, including the `docs/ai-usage-report.md` log entry each step appends |
| `release` skill | `.agents/skills/release/SKILL.md`, `.claude/skills/release/SKILL.md` | Invoke the `release` skill (e.g. `/release`) | Walks a push to `main` through CI to a verified Render deploy, and names the two rollback paths if `deploy` fails |
| `incident-response` skill | `.agents/skills/incident-response/SKILL.md`, `.claude/skills/incident-response/SKILL.md` | Invoke the `incident-response` skill (e.g. `/incident-response`) | Diagnoses a live production problem, decides rollback vs. fix-forward, and writes the entry to `ops/incidents/` |
| Canonical/working-copy sync | `.agents/agents/`, `.agents/skills/` (canonical) kept aligned with `.claude/agents/`, `.claude/skills/` (working copy) via root `Makefile` and `scripts/check-agents-sync.sh` | Run `make sync-agents`, then `bash scripts/check-agents-sync.sh` | Copies canonical subagent/skill files into the tree Claude Code actually loads, and fails CI's `agents-sync` job if the two trees ever drift apart |

Later issues extend this table as new subagents and skills are added.
