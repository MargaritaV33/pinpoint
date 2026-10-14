# Agent capabilities

This project defines its own subagents and skills for Claude Code (and
the course's cross-assistant convention) to use. They describe this
project's own already-documented process — grooming, implementation, QA,
release, and incident response — rather than inventing anything new. See
`docs/agent-extension-pack.md` for the full capability table.

## Two trees, one source of truth

- **`.agents/`** — the canonical copies: `.agents/agents/*.md` (subagent
  definitions) and `.agents/skills/*/SKILL.md` (skill definitions). This
  is the directory to edit.
- **`.claude/`** — the real, non-symlinked working copy Claude Code
  actually loads: `.claude/agents/*.md` and `.claude/skills/*/SKILL.md`.
  Never edit these directly; they are generated from `.agents/`.

Both trees contain real files, not symlinks — this repo is developed on
Windows, where symlinks are unreliable without extra privileges.

## Keeping them in sync

- `make sync-agents` copies every file under `.agents/agents/` into
  `.claude/agents/` and every file under `.agents/skills/` into
  `.claude/skills/`, removing anything on the `.claude/` side that no
  longer exists on the `.agents/` side. Run this after editing anything
  under `.agents/`.
- `bash scripts/check-agents-sync.sh` diffs the two tree pairs
  (`.agents/agents` vs. `.claude/agents`, `.agents/skills` vs.
  `.claude/skills`), prints what differs if anything does, and exits
  non-zero on any difference. A CI job, `agents-sync` in
  `.github/workflows/ci.yml`, runs this script on every push and pull
  request so a drift between the two trees shows up as its own failing
  check, independent of the application test suites.

Workflow: edit under `.agents/`, run `make sync-agents`, then
`bash scripts/check-agents-sync.sh` to confirm the trees match before
committing.

## What is not synced

`.claude/settings.json` (which wires the hooks) and `agent-hooks/` are not part
of either tree: `make sync-agents` only removes and re-copies `.claude/agents`
and `.claude/skills`, so it never touches them. The hooks are described in
`agent-hooks/README.md`; what agents may do alone is in `docs/permissions.md`;
`custom-agent/README.md` references the `on-call-responder` subagent that lives
in the trees above.
