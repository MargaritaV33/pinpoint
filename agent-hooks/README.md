# Agent hooks

Two small Claude Code hooks that fence agent sessions in this repo:

- **`pretool_bash_guard.py`** (PreToolUse, tool `Bash`) blocks a short list of
  accident-prone shell commands.
- **`posttool_test_reminder.py`** (PostToolUse, tools `Edit`, `Write`,
  `MultiEdit`) reminds the agent which test command to run after it edits
  `backend/` or `frontend/`. It prints a reminder and never runs anything.
- **`run.sh`** is the single entry point both hooks are started through.

These are **guardrails against accidents, not a security boundary.** They match
on the shell string. The section "What the hooks cannot enforce" below, and
`docs/permissions.md`, list what they miss. Python standard library and POSIX
`sh` only: no dependency was added and `uv` is not used.

| File | Role |
|---|---|
| `pretool_bash_guard.py` | The guard: five rules, below |
| `posttool_test_reminder.py` | The test reminder |
| `run.sh` | Launcher: picks a working Python, then runs the script |
| `tests/` | `unittest` tests; run with `make hooks-test` |
| `../.claude/settings.json` | Wires the two hooks into Claude Code |

## The contract

Both scripts read the hook's JSON from stdin (`tool_name`, `tool_input`, `cwd`).

| Exit code | PreToolUse guard | PostToolUse reminder |
|---|---|---|
| `0` | Allow. No output. | Done. Prints a JSON reminder, or nothing. |
| `2` | **Deny.** stderr is the message; Claude Code shows it to the agent. | Never used. |
| `1` | Internal problem. **Fail-open:** one warning line on stderr, the command is **not** blocked. | Same: one warning line, nothing blocked. |

A non-`Bash` `tool_name` is allowed. An internal problem (stdin is not JSON,
no `tool_input.command`, an unexpected exception) never produces exit `2`.

A command that cannot be parsed (for example an unbalanced quote) is not waved
through: the guard falls back to matching the raw text against the same rules,
and the denial says so.

### Deny message style

The message is the user interface of a guardrail: it names the rule, quotes the
offending part and says what to do instead.

```text
pinpoint guard: BLOCKED by rule 1: no force push to main.
  Offending part: git push --force origin main  (force push to main)
  Instead: Name a feature branch instead: git push --force-with-lease origin feature/x.
  See agent-hooks/README.md and docs/permissions.md. This is a guardrail against accidents, not a security boundary.
```

For rule 3 only the file name is quoted, and for rule 5 the deploy URL is never
echoed (it is a secret), so a denial does not copy a secret into the transcript.

## The rules

| # | Rule | Denied (examples) | Allowed (examples) |
|---|---|---|---|
| 1 | No force push to `main` / `master`, and no deleting it | `git push --force origin main`, `-f`, `--force-with-lease origin main`, `git push origin +main`, `--force origin HEAD:main`, `--force origin refs/heads/main`, a force push with **no** refspec (it may target the current branch), `git push origin --delete main`, `git push origin :main` | `git push origin main`, `git push`, `git push --force-with-lease origin feature/x`, `git push -f origin my-branch` |
| 2 | `_local/` is read-only for the shell | `rm`, `mv`, `cp` into it, `touch`, `truncate`, `sed -i`, `tee`, `>` / `>>`, `git clean`, `git checkout --` aimed at it, in any spelling (`_local/x`, `./_local/x`, `"_local/x"`, `_local\x`, this repo's absolute path plus `/_local/`) | `cat _local/make-it-better.md`, `ls _local`, `grep -n foo _local/make-it-better.md` |
| 3 | Real `.env` files stay out of the shell | any command other than a small non-printing list (`ls`, `test`, `stat`, `wc`, `git`, `docker`, `make`, ...) whose arguments name `.env`, `./.env`, `backend/.env`, `"$PWD/.env"`, `.env.local`, `.env.production`; `>` / `>>` / `<` on them; `cp .env.example .env` | `cat .env.example`, `grep -n JWT .env.example`, `docker compose up`, `make up` |
| 4 | No recursive `rm` outside the repo | `rm -rf /`, `~`, `$HOME`, `..`, `../other`, `/tmp/x`, `C:\Users\x`, `/c/Users/x`; flags split across words; a target with a variable, `$(...)`, backticks or brace expansion (the message says it cannot be resolved) | `rm -rf node_modules`, `rm -rf ./frontend/dist`, `rm -rf backend/.pytest_cache`; a plain `rm file` outside the repo |
| 5 | The Render deploy hook is CI's job | `curl`, `wget`, `Invoke-WebRequest`/`iwr`, `Invoke-RestMethod`/`irm` whose arguments contain `render.com/deploy` or `RENDER_DEPLOY_HOOK_URL` (`$...`, `${...}`, `%...%`, `$env:...`) | `curl http://localhost:8100/health`, `curl https://<anything>.onrender.com/health`, `gh run list` |

Details worth knowing:

- Rule 4 resolves each target without following symlinks. Relative targets
  resolve against the `cwd` from the hook input; `..` is normalised; the repo
  root comes from **this script's own location**, never from `cwd`. A target
  equal to the repo root itself is denied.
- The script never reads the secret behind rule 5 or rule 3. It only looks at
  the text of the command.
- Quoted text, comments and heredoc bodies are data, not commands:
  `git commit -m "never git push --force origin main"` is allowed. `$(...)`
  and backticks are scanned as commands of their own.
- A rule applies to the command word after `sudo`, `env`, `xargs`, `time`,
  `command`, leading `VAR=value` and similar wrappers.

## The launcher and the fail-open decision

Both hooks are started as `sh "$CLAUDE_PROJECT_DIR/agent-hooks/run.sh" <script>.py`.
The path is quoted because this repo can live in a folder with spaces
(`Pinpoint_AI Dev Tools`). The launcher tries `python3`, then `python`, and uses
a candidate only if a probe run (`<candidate> -c "import sys;
sys.exit(0 if sys.version_info >= (3, 8) else 1)"`) succeeds. On a Windows
machine `python3` is often the Microsoft Store stub, which exists on `PATH` but
does not run Python; the probe fails, it is skipped, and `python` is used. It
does not use `uv`, the `py` launcher or an absolute path.

**No interpreter found is fail-open, by decision.** The launcher exits `1` (a
non-blocking error) with a message that says the guardrails are **NOT** active
and what to install. Reason: the hooks are guardrails against accidents, and a
fail-closed launcher would block every Bash command on a machine without
Python, including the one the agent would use to fix it, which pushes people to
delete the hook. The trade-off is plain: on a machine without Python the
guardrails are silently absent apart from that one stderr line.

On the dev machine (Windows 11, Git Bash, `python` 3.14, `python3` the Store
stub, no `uv`) the launcher, run with a `PATH` that has `sh` but no Python,
printed the message above and exited `1`. The evidence is in a comment on issue
#22.

## Tests

```bash
make hooks-test
# or, with no make and no install:
python -m unittest discover -s agent-hooks/tests
```

`make hooks-test` uses whichever of `python3` / `python` passes the launcher's
probe and does not call `uv`. The tests call each script as a subprocess with
real stdin JSON and assert the exit code and stderr, so the exit-code contract
is tested, not just a function. They also run `run.sh` (with fake `PATH`s that
reproduce the Store stub and a missing Python) and the exact command line from
`.claude/settings.json` through `sh -c` the way Claude Code starts it.

CI has a `hooks` job (`.github/workflows/ci.yml`: ubuntu, `actions/setup-python`,
no `uv`) that runs the same tests and then calls the launcher itself. Like
`agents-sync` and `mcp` it is deliberately not in `stack.needs` or
`deploy.needs`; gating the deploy on it is the owner's decision.

## Live proof

A unit test shows the script denies; it does not show Claude Code actually
calls it. Issue #22 carries a comment with a real fresh headless Claude Code
session in which `git push --force origin main` and `cat .env` were blocked by
this guard's own messages, a control `cat .env.example` ran, and the PostToolUse
reminder reached the agent after a `Write` under `backend/`.

## How to add a rule

1. Write the rule as a function that takes the parsed command and returns a
   list of `Violation(rule_number, quoted_part, instead)`. Look at `rule5_render`
   for the smallest example.
2. Add its name to `RULE_NAMES` and call it from `check_command`.
3. Quote as little as you can. If the rule is about a secret, quote only a
   name, never a value.
4. Add at least one deny and one allow case to
   `tests/test_pretool_guard.py`, including the spelling that would slip
   through a naive match. Run `make hooks-test`.
5. Add a row to the rule table here and in `docs/permissions.md`.

## Using it from another assistant

Any assistant that can run a command before a shell tool call can reuse the
guard, because the contract is small: the command receives the tool call as
JSON on stdin; **exit `2` blocks** the call; **stderr is the message** the
assistant is shown; exit `0` allows.

Claude Code (this repo, tested): in `.claude/settings.json`

```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash",
        "hooks": [ { "type": "command",
                     "command": "sh \"$CLAUDE_PROJECT_DIR/agent-hooks/run.sh\" pretool_bash_guard.py" } ] }
    ]
  }
}
```

Other assistants (Codex, Cursor, Gemini CLI and similar): their hook
configuration formats, the JSON field names they send, and whether they honour
exit `2` with stderr were **not verified**. The guard reads `tool_name`,
`tool_input.command` and `cwd`; an assistant that names these differently needs
a small adapter in front of it, which is not written here.

## What the hooks cannot enforce

Honest list; the full version, with the owner-only list, is in
`docs/permissions.md`.

- Matching is on the shell string. `bash -c "..."`, `eval`, a script that is
  written and then run, a variable that holds a path, and `cd _local && rm x`
  are **not** caught. Neither is `find ... -exec rm`, `python -c "..."` or any
  other program that does the deleting or reading itself.
- Only the **Bash tool** is hooked. The Edit and Write tools and the PowerShell
  tool are not covered, so `_local/` and `.env` can still be changed through
  Edit/Write.
- `echo $JWT_SECRET` and `printenv` are not blocked: the guard looks at file
  names, not at the environment.
- A person can disable the hooks in `.claude/settings.local.json`.
- The launcher is fail-open: with no working Python, or on any internal
  problem, the command runs unchecked after one warning line.
- Rules 2 to 4 reason about paths as text. Symlinks are not followed.

The real enforcement for the owner-only list (the Render dashboard, GitHub
secrets) is the owner's own account permissions, not these hooks.
