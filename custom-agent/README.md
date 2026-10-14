# custom-agent: the `on-call-responder` subagent

This folder is a **reference**, not a copy. The agent is defined in
`.agents/agents/on-call-responder.md` (canonical) and
`.claude/agents/on-call-responder.md` (the working copy Claude Code loads),
and it stays there: Claude Code loads subagents only from `.claude/agents/`, and
`scripts/check-agents-sync.sh` plus the CI `agents-sync` job require the two
trees to match, so moving the file would break both. See
`agent-capabilities/README.md` for how the trees stay in sync, and
`docs/agent-extension-pack.md` for the full capability table.

## What it does

Given a production symptom (a bad `/health` shape, a failed `deploy` job, 5xx
responses from Render) it diagnoses it using `docs/deployment.md` and
`docs/release-process.md` as its runbook and **proposes** the fix.

**Hard rule: it proposes and never acts.** It never runs `git push`, `git revert`
followed by a push, Render's **Redeploy** or a restart. Its output is the exact
command or dashboard action a human should take, then it stops. The rule is in
the agent's own instructions and is backed by its tool list.

## What it can use

`Read`, `Grep`, `Glob` and `WebFetch` only (the `tools:` line of its definition;
the session's init event in the example run listed exactly these four). It has
no `Bash`, `Edit` or `Write`, so it cannot run a command or change a file even
if it wanted to.

## How to launch it

Interactively, in Claude Code started in the repo root: ask for it by name
(`use the on-call-responder subagent to look at this symptom: ...`) or pick it
with `/agents`.

Headless, as in the example below (a fresh `claude -p` session that *is* the
agent, with its tools restricted to the read-only ones):

```bash
claude -p "$(cat prompt.txt)" --agent on-call-responder \
  --allowedTools "Read,Grep,Glob" --output-format stream-json --verbose > run.jsonl
```

## Example run: the issue #12 incident

A real run, not edited: the model's text and the tool calls are exactly what the
session produced. What was changed, and why, is listed under "Honest limits".

| | |
|---|---|
| Date | 2026-10-14 |
| Repository commit it read | `34a75a8` (a fresh clone of the repo at that commit; `git rev-parse --short HEAD`, clean working tree) |
| Client and model | Claude Code 2.1.299, `claude-sonnet-5-5` |
| Launch command | the headless command above, run from the root of that clone, with `prompt.txt` holding the input below |

### Input given to the agent

One framing line, then the text of the issue #12 reopening comment copied from
`gh issue view 12 --comments` (the fourth comment, "Reopened: the Render deploy
failed."). The later Engineer and QA comments were **not** given to the agent.

```text
Production symptom, reported as the reopening comment on GitHub issue #12 (verbatim):

Reopened: the Render deploy failed.

Log from the Render dashboard:

    ==> Deploying...
    sh: 1: DATABASE_URL="postgresql://pinpoint:...@dpg-.../pinpoint_xxuj" uv run uvicorn app.main:app --host 0.0.0.0 --port 8100: not found
    ==> Exited with status 127

Root cause: render.yaml's dockerCommand invokes `uv`, which is not present
in the runtime stage of the Dockerfile (the image runs uvicorn from the
venv directly, not via `uv run`). The local verification pass (QA's
subprocess simulation of dockerCommand) exercised the sed rewrite and the
shell quoting in isolation, but never actually ran the command inside the
real built image — so the missing `uv` binary in the runtime stage was
never caught.

Fix, specified by the repo owner:
- Do not override the image's command in render.yaml at all. Remove
  dockerCommand entirely; the Dockerfile's own CMD stays the single source
  of truth for how the container starts.
- Move the postgres:// -> postgresql+psycopg:// normalisation out of
  render.yaml and into backend/app/config.py: accept both URL forms there
  (as the reference app does), with a unit test covering the normalisation.
- Verify the actual image runs, for real this time: `docker build` the
  image, then `docker run` it locally with DATABASE_URL set to a bare
  postgresql:// URL pointed at the compose Postgres service, and confirm
  GET /health returns 200 from the running container.

Lifecycle for this fix: Engineer -> QA -> push. Append the outcome,
including the lesson that mocked/simulated verification missed a
runtime-image gap that only running the real container would have caught,
to docs/ai-usage-report.md.
```

### What the agent did

Twelve tool calls, all `Read`, `Glob` or `Grep` (paths shortened to `<clone>`;
the tool results are the contents of those files and are omitted here for length):

```text
TOOL CALL: Read {"file_path": "<clone>\\docs\\deployment.md"}
TOOL CALL: Read {"file_path": "<clone>\\docs\\release-process.md"}
TOOL CALL: Read {"file_path": "<clone>\\render.yaml"}
TOOL CALL: Glob {"pattern": "**/Dockerfile*", "path": "<clone>"}
TOOL CALL: Read {"file_path": "<clone>\\backend\\app\\config.py"}
TOOL CALL: Read {"file_path": "<clone>\\Dockerfile"}
TOOL CALL: Grep {"pattern": "dockerCommand|uv run uvicorn", "path": "<clone>", "output_mode": "content", "glob": "!{node_modules,.git,.venv}/**"}
TOOL CALL: Grep {"pattern": "postgres(ql)?://|normali", "path": "<clone>\\backend\\tests", "output_mode": "content"}
TOOL CALL: Grep {"pattern": "deploy|health|RENDER", "path": "<clone>\\.github\\workflows\\ci.yml", "output_mode": "content", "-n": true}
TOOL CALL: Read {"file_path": "<clone>\\docs\\ai-usage-report.md", "offset": 50, "limit": 30}
TOOL CALL: Read {"file_path": "<clone>\\docs\\ai-usage-report.md", "offset": 680, "limit": 120}
TOOL CALL: Read {"file_path": "<clone>\\backend\\app\\routers\\health.py"}
```

No `Bash`, `Edit` or `Write` call exists in the run, and the agent ran no
`git push`, `git revert`, Redeploy or restart. Its own closing line says so too.

### The agent's full output

Its text before the first tool call:

```text
I'll start with the two runbook docs and the files the issue comment names.
```

Its final answer:

````text
**Diagnosis: the defect in the issue comment is real, but the stated root cause is wrong. The fix is already in the working tree, so what's left is verifying it deployed.**

**1. The root cause is `dockerCommand`, not a missing `uv`**
- The Dockerfile's runtime stage does install `uv` (`RUN pip install --no-cache-dir uv`, line 37).
- If `uv` were missing, the error would read `sh: 1: uv: not found`. The log instead names the whole string, `DATABASE_URL="postgresql://…" uv run uvicorn …: not found`, so it was looked up as one program name.
- That points at how Render invoked the old `dockerCommand` override, not at the image contents. I couldn't see the old `dockerCommand` text, since it's no longer in `render.yaml`, so this is an inference from the log.
- The repo's own records already say this. The `render.yaml` header comment and the 2026-10-14 entry in `docs/ai-usage-report.md` both correct the `uv` claim. Don't re-do the fix on the `uv` theory.

**2. The prescribed fix is already in place**
- `render.yaml` has no `dockerCommand`, so the Dockerfile's `CMD ["/app/backend/.venv/bin/uvicorn", …]` is the only start path.
- `backend/app/config.py` has a `database_url` field validator that rewrites `postgres://` and `postgresql://` to `postgresql+psycopg://`.
- `backend/tests/test_config.py` covers the normalisation.
- `docs/ai-usage-report.md` already records the outcome and the lesson. It says the real build and run against Postgres passed and that `406a48d` and `5117c40` were pushed.

I haven't repeated the Docker build or run, because I only read files and can't run commands.

**3. One leftover to fix**
- `docs/deployment.md` still describes the old design:
  - Line 26 says "`render.yaml`'s `dockerCommand` is the only command Render runs".
  - Line 43 says the scheme is rewritten "inside `dockerCommand`".
- Both contradict `render.yaml`, and the `DATABASE_URL` row should point at `config.py` instead. I don't edit files, so an engineer needs to make this change.

**4. What a human should check on Render, by hand**
There's no log-streaming command for this setup.
1. Open the `pinpoint` service in the Render dashboard and check the **Deploys** tab. The newest deploy should be built from a commit at or after `5117c40`, and it should be Live.
2. Check **Settings → Docker Command**. It should be empty. The fix removed the key from `render.yaml`, but I can't confirm Render cleared a value it had already synced, so look.
3. Read the **Logs** tab for uvicorn starting on port 8100 and no exit 127 or `ModuleNotFoundError`.
4. Confirm `GET <PUBLIC_URL>/health` returns `{"status":"ok","commit":"<sha>"}` matching the fix commit. This is the same check the CI `deploy` job polls. A slow first response is the accepted free-plan cold start from `docs/deployment.md`, not an incident.

**5. Rollback (probably not applicable)**
- **Redeploy a previous build:** per `docs/release-process.md`, this means the Deploys tab and a previous successful deploy's **Redeploy**. #12 was the first-ever deploy, so there is probably no earlier successful build to go back to. Check the Deploys tab before relying on it.
- **Roll forward:** `autoDeployTrigger: off` means nothing deploys until CI's `deploy` job calls the hook. Make sure the fix commits are on `main` and `backend`, `frontend` and `stack` are green. Then `deploy` fires and its `/health` commit check tells you whether the fix is live.
- If CI is green but nothing deployed, check the `RENDER_DEPLOY_HOOK_URL` secret and the `PUBLIC_URL` variable. I can't see either.

I haven't pushed, redeployed or restarted anything. I haven't done the issue's Engineer → QA → push steps either, because they're already done. Pushing and redeploying are yours to do.
````

### What it proposed

It proposed no command to run. Its proposals are dashboard checks for a human,
quoted from the answer above:

- "Open the `pinpoint` service in the Render dashboard and check the **Deploys**
  tab. The newest deploy should be built from a commit at or after `5117c40`,
  and it should be Live."
- "Check **Settings → Docker Command**. It should be empty."
- "Read the **Logs** tab for uvicorn starting on port 8100 and no exit 127 or
  `ModuleNotFoundError`."
- "Confirm `GET <PUBLIC_URL>/health` returns `{"status":"ok","commit":"<sha>"}`
  matching the fix commit."
- Rollback: the **Redeploy** of a previous successful build from the Deploys
  tab (from `docs/release-process.md`), with the remark that "#12 was the
  first-ever deploy, so there is probably no earlier successful build to go back
  to"; otherwise roll forward through CI.
- One follow-up for an engineer: `docs/deployment.md` still says
  `dockerCommand` is the only command Render runs (line 26) and that the scheme
  is rewritten "inside `dockerCommand`" (line 43).

### Compared with what actually happened

The reopening comment named the cause: `uv` "is not present in the runtime stage
of the Dockerfile". The Engineer and QA comments that follow it on #12 (not given
to the agent) corrected that: `uv` **is** installed in the runtime stage and the
Dockerfile's own `CMD` ran fine in a real `docker build` and `docker run`; the
defect was the `dockerCommand` override in `render.yaml`, which Render appears to
have treated as one long executable name. The fix removed `dockerCommand`
(`406a48d`) and moved the `postgres://` normalisation into `Settings`
(`5117c40`).

- **It did not repeat the stated cause.** It said the stated root cause "is
  wrong", pointed at the Dockerfile line that installs `uv`, and reasoned from
  the shape of the log: with `uv` missing the error would read
  `sh: 1: uv: not found`, but the log names the whole string, so the string was
  looked up as one program name. That is the same reasoning the Engineer gave.
- **That is not an independent finding.** The agent read `render.yaml` and
  `docs/ai-usage-report.md`, which at the commit it read already record the
  correction, and its answer says so ("The repo's own records already say
  this"). So the run shows it reaches the corrected cause and checks it against
  the Dockerfile, but it cannot show it would have found it blind.
- **It diagnosed from the log text, not from the live defect.** `render.yaml` at
  `34a75a8` no longer contains `dockerCommand` (the fix is `406a48d`), and the
  agent says "I couldn't see the old `dockerCommand` text, since it's no longer
  in `render.yaml`, so this is an inference from the log". This example does not
  run it against a checkout from before `406a48d`: that tree has no `docs/release-process.md` and no
  `on-call-responder` definition, so it would not exercise the agent as it is
  used.
- **What it missed or could not know.** Why Render mis-parsed the override: the
  Engineer also left that unexplained ("I didn't chase the exact Render-side
  parsing quirk"). It treated "fix already pushed, verify the deploy" as the
  state of the world because the records said so, and it could not see Render's
  dashboard, so its "Docker Command should be empty" check and its guess that
  Render might not clear a previously synced value are suggestions, not
  findings; nobody checked them.
- **What it found that the Engineer and QA of #12 did not.** The stale
  `docs/deployment.md` lines 26 and 43. They are real: `grep -n dockerCommand
  docs/deployment.md` matches both at `34a75a8`. Fixing them is outside issue
  #22, so they are reported, not changed here.

### Honest limits of this example

- One run, one incident, one model. It shows the agent staying read-only and
  producing a sensible plan; it does not measure how good its diagnoses are.
- The only edits to the raw session output are: the clone directory path is
  replaced by `<clone>` in the tool-call list and the tool results are left out.
  The agent's own text is verbatim. The raw event stream is not committed.
- The headless run printed a one-line warning that it received no stdin and
  proceeded without it. It did not affect the run.
- `grep -n "postgresql://" custom-agent/README.md` matches only the truncated
  `postgresql://pinpoint:...@dpg-.../pinpoint_xxuj` of the reopening comment and
  the agent's own quotations of the scheme; no full credential appears.
