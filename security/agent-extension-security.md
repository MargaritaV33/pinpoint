# Agent extension security

Issue #26, rubric criterion 13. Written by an AI reviewer (Claude Code, as the
Engineer subagent of this repository's process, model `claude-sonnet-5-5`) from
the files named in each risk. A reader can open each file and see what is
cited. Every statement about enforcement says what enforces it today or says
"not enforced"; proposals are marked as proposals. Nothing here relies on how a
particular Claude Code build behaves beyond what a file in this repository
says.

## Verdict first

The controls around the agents in this repository are **guardrails against
accidents, not a security boundary** (the repository's own phrase:
`docs/permissions.md:5-6`, `agent-hooks/README.md:12-13`). They stop a
well-meaning agent from a short list of slips. They do not stop an agent that has
been steered by hostile text.

What a hostile issue comment or pin comment could cause **today**: anything an
agent with a shell, the Edit and Write tools and the owner's `git` and `gh`
access can do inside the repository, because `docs/permissions.md:15` lets it
push to `main` unprompted, `main` has no branch protection and no code owners,
and a push to `main` with green `backend`, `frontend` and `stack` jobs deploys to
production (`.github/workflows/ci.yml:237-240`, `docs/permissions.md:15`). That
includes changing application code, changing the CI file, changing the agent
definitions themselves, reading local secrets through paths the hooks do not
cover (risk 3) and sending text to the network. The only technical brakes on that
path are the five hook rules (no force push to `main`, `_local/` and `.env`
shell access, recursive `rm`, the Render hook URL) and the CI test jobs. The QA
gate in `_docs/process.md` is a convention carried out by the orchestrator, not a
technical control.

What would reduce it, each **a proposal, none of it present**: restricting
subagent `tools:` lists, a read-only credential for the MCP server (both in
#36), branch protection with required reviews and code owners (#28), and
Edit/Write/PowerShell hooks plus `permissions.deny` rules (parked:
`_local/make-it-better.md`, row 16; the `cp .env.example .env` overwrite guard
is row 17).

## Risk 1: prompt injection through text agents read

**Source files.** The process makes GitHub issues the input to every role:
`_docs/process.md:3` ("Tasks are GitHub issues"), `_docs/team/pm.md:5`
(PM reads "the issue as written"), `_docs/team/software-engineer.md:5` (Engineer
"Read the issue and implement what it describes"),
`.claude/skills/implement-issue/SKILL.md:12-13` (orchestrator takes the next
open issue), and `docs/permissions.md:16` names `gh issue create` and `gh issue
comment` as things an agent does unprompted. The repository is public
(`gh repo view` reports `visibility: PUBLIC`, issues enabled). On 2026-10-14 `gh` listed only the owner's account as author of every issue
and of the comments it returned; nothing in the repository restricts who may
comment (GitHub interaction limits were not checked). Text
from any other account would reach an agent through `gh issue view` exactly as
the owner's does.

**Path A: GitHub issues and comments.**

1. A comment or issue body contains instructions.
2. An agent reads it with `gh` as part of its normal task. The PM then rewrites
   the issue (`_docs/team/pm.md:6`), which can carry the text forward into the
   groomed body the Engineer treats as the specification.
3. The Engineer edits files (Edit/Write are not hooked, risk 3) and commits.
4. `docs/permissions.md:15` allows `git push` to `main` without asking.
5. If `backend`, `frontend` and `stack` pass, the `deploy` job calls the Render
   deploy hook (`ci.yml:237-243`) and the change is live.

**Path B: the MCP server returns client-written text verbatim.**

1. A client with only a guest link can post pin text and comments
   (`backend/app/routers/guest.py:46-97,100-137`; the guest token is the
   credential, and the text has no length limit, see `pr-audit.md` A-11).
2. `open_pins` returns the studio export "**verbatim** (not parsed)"
   (`mcp-server/README.md:24`); the export includes each open pin's first comment
   text (`backend/app/export.py:33-40`).
3. The text enters the context of the Claude Code session that called the tool,
   a session that normally also has Bash, Edit and Write (the MCP server is only
   one tool among them).
4. From there: edits, a commit, a push to `main`, a deploy, as in Path A steps
   3 to 5.

**What exists against this chain today.** Nothing that inspects text for
instructions. Hook rule 1 blocks a force push to `main` (a normal push is
allowed). Hook rule 5 blocks a shell command that names the Render deploy URL
(CI does the deploy anyway). The MCP server's tool descriptions state that it is
read-only (`mcp-server/README.md`, "Tools"), which says nothing about what the
session does afterwards with the text. QA and the orchestrator reviewing the
result is a convention (`_docs/process.md`, "Rules"), not enforced.

## Risk 2: MCP server token scope

**What is enforced, and where.** Read-only is enforced **in the server's code
and tests**, not by the credential:

- The client issues only GET requests plus `POST /auth/login`
  (`mcp-server/src/pinpoint_mcp/client.py:14`);
  `mcp-server/tests/test_readonly.py:66` asserts every request across all tools is
  a GET except the login POST, and `:96` asserts the client module can issue
  nothing else.
- The tools are annotated read-only and the server instructions say so
  (`test_readonly.py:31,39`).
- No secret and no `guestToken` appears in a tool result
  (`mcp-server/tests/test_secrets.py:33-71`; `mcp-server/README.md:24` says
  `list_rooms` never returns `guestToken`).

**What is not enforced.**

- The credential is an ordinary studio login. `PINPOINT_TOKEN` or
  `PINPOINT_EMAIL` and `PINPOINT_PASSWORD` (`.mcp.json:8-10`) are a normal bearer
  token with the studio user's full rights over the API. The backend has no token
  scopes: the token carries only `sub`, `iat` and `exp`
  (`220f89a:backend/app/auth/jwt.py:21-28`).
- Those variables sit in the shell environment of whoever starts Claude Code.
  `printenv` and `echo $VAR` are not blocked (`agent-hooks/README.md:204-205`,
  `docs/permissions.md`, "What the hooks cannot enforce").
- `PINPOINT_BASE_URL` can point anywhere, including production: the client has no
  check and `.mcp.json:7` only supplies a localhost default. Nothing enforces
  local-only use.
- `.mcp.json:4-5` runs `uv run --directory mcp-server pinpoint-mcp`, so what runs
  on the machine of whoever approves the server is code from this repository. The
  README says the client asks once to approve the project-scoped server
  (`mcp-server/README.md`, "In Claude Code"). Nothing in the repository reviews a
  later change to `.mcp.json` or `mcp-server/` before it reaches that machine: no
  code owners file exists and `main` is not protected (#28).
- The demo credentials used in the README example are public
  (`mcp-server/README.md`, "In Claude Code"); with them the above is harmless. With
  a real studio account the same configuration gives a session full write access
  to that studio's data.

Proposal, not present: a read-only credential for the MCP server (#36).

## Risk 3: hook bypass paths, and what the guardrails do not cover

The hooks are wired in `.claude/settings.json`: a `PreToolUse` hook with matcher
`Bash` (`:5`) and a `PostToolUse` hook for `Edit|Write|MultiEdit` that only prints
a reminder (`:16`). There is no `permissions` block in that file.

The "not covered" list below is exactly the one in
`agent-hooks/README.md:192-216` (section "What the hooks cannot enforce") and
`docs/permissions.md:75-96` (section "What the hooks cannot enforce"). The last
column says which of the two files carries each item:

| Not covered | Carried by |
|---|---|
| Matching is on the shell string: `bash -c`, `eval`, a script written and then run, a variable that holds a path, `cd _local && rm x`, `find ... -exec rm`, `python -c "..."` | both files, first bullet |
| Only the Bash tool is hooked: Edit, Write and PowerShell are not covered, so `_local/` and `.env` can still be changed through Edit/Write | both files, "Only the Bash tool is hooked" |
| `echo $JWT_SECRET` and `printenv` are not blocked | both files, `echo $JWT_SECRET` bullet |
| Readers that reach a real env file without naming it: `cat $F`, `grep -r JWT .`, `git grep` | `agent-hooks/README.md` only, the `find ... -name ".env*" -exec` bullet |
| `cp .env.example .env` overwrites an existing `.env` and is not refused (parked: `_local/make-it-better.md`, row 17) | `agent-hooks/README.md` only, the `cp .env.example .env` bullet |
| A person, or an agent that can edit it, can turn the hooks off in `.claude/settings.local.json` | both files, "disable the hooks" bullet |
| The launcher is fail-open: with no working Python, or on any internal problem, the command runs unchecked after one warning line | both files, "fail-open" bullet |
| Symlinks are not followed; paths are compared as text | both files, paths-as-text bullet |
| The test reminder is not a test run | `docs/permissions.md` only, last bullet |
| Guarding Edit, Write and PowerShell is parked (`_local/make-it-better.md`, row 16) | `docs/permissions.md`, "Only the Bash tool is hooked" bullet |

**New in this document** (follows from the files named; not in either list):

- The `Read` tool is also not hooked. This follows from "only Bash is hooked":
  `.claude/settings.json` has a `PreToolUse` matcher for `Bash` only. Hook rule 3
  stops `cat .env` in the shell, not a file read through a different tool.
- Network is covered by one rule only: rule 5, which looks for the Render deploy
  URL in `curl`/`wget`/`Invoke-WebRequest`/`Invoke-RestMethod` commands
  (`agent-hooks/README.md`, "The rules"). Any other `curl`, and the `WebFetch`
  tool given to `on-call-responder` (risk 4), can send text anywhere.
- `gh` is allowed by `docs/permissions.md:16` and the hooks inspect `git push`
  only (rule 1); `gh api` and `gh issue close` are not inspected.
- Nothing in `.claude/settings.json` stops an agent editing the agent
  definitions, the hooks or the CI file (see risk 4); `docs/permissions.md:32` lists
  turning the hooks off as an owner action, which is a convention.

## Risk 4: subagent and skill definitions are instructions in the repository

Files: `.claude/agents/*.md` and `.agents/agents/*.md` (identical trees),
`.claude/skills/*` and `.agents/skills/*`.

- `pm`, `qa-engineer` and `software-engineer` carry **no `tools:` line**
  (`.claude/agents/pm.md`, `qa-engineer.md`, `software-engineer.md`: front matter
  has only `name` and `description`). The files declare no restriction on what
  those subagents may use. Their bodies are one line, "Read your role definition
  from `_docs/team/<role>.md` and follow `_docs/process.md`" (`:6`), so the real
  instructions are `_docs/team/*.md` and `_docs/process.md`: changing those files
  changes what the agents do.
- `on-call-responder` is the only restricted one: `tools: Read, Grep, Glob,
  WebFetch` (`.claude/agents/on-call-responder.md:4`). **What that allows:** reading
  any file the Read tool can open (the hooks do not cover Read, so that includes
  `.env` and `_local/`, see risk 3) and requesting any URL; text read from a file
  can leave in a request. **What it does not allow:** editing a file, running a
  shell command or pushing; it cannot change the repository or call `gh`. Its
  description says it "never runs a destructive, deploy, or rollback command"
  and that is true because it has no tool that runs commands, not because the
  text asks.
- `scripts/check-agents-sync.sh` (CI job `agents-sync`, `ci.yml:118-124`) checks
  that `.agents/` and `.claude/` are identical (`diff -rq`). It checks the two
  trees match, **not that the content is safe**. A malicious edit made to both
  trees passes.
- Nothing requires owner review of these files: there is no CODEOWNERS file
  (`git ls-files` finds none) and `main` is not protected (the branch-protection
  API answers HTTP 404, "Branch not protected"). Tracked in #28; the specific
  proposal for agent definitions is #36.

## What is and is not claimed

- Claimed: each cited line exists in the file named, as of the commit this
  document was written against.
- Not claimed: that any of these paths has been exploited, or that the
  controls named here fail in practice. The point is that they are not
  designed to hold against hostile input, and the repository says so itself.
- Not covered: how a given Claude Code build labels or sanitises subagent reports,
  or what its permission prompts do. That is not in the repository, so it is
  left out.
- Other assistants (Codex, Cursor, Gemini CLI and similar) were not verified
  here (`agent-hooks/README.md`, "Using it from another assistant").
