# 2026-10-14: first Render deploy crashed at start (exit 127)

Blameless postmortem. Actors are roles and systems ("the owner", "the agent",
"QA", "the Blueprint"); no person is named. Every time is UTC. Sources are in
brackets. Where the repo does not record something it says so.

Related: [runbook](../runbook.md) ·
[the platform outage the same day](2026-10-14-render-platform-outage.md)
(a different failure, seen differently: there the CI `deploy` job went red at
"Trigger Render deploy" with HTTP 500 and `/health` did not answer; here the
`deploy` job did not exist yet and the crash showed in the Render dashboard log).

## Summary

The first deploy of the `pinpoint` web service on Render crashed during
start with `sh: 1: ... uv run uvicorn ...: not found` and `Exited with
status 127`. The cause was a `dockerCommand` override in `render.yaml` that
Render treated as one executable name instead of a shell script. The
override was removed and the database-scheme rewrite it performed moved into
the application's `Settings`, and the image was then verified by building and
running it for real. [issue #12, reopening comment and fix comment]

## Timeline

| Time (UTC) | Event | Source |
|---|---|---|
| 14 Oct, 08:58 | `render.yaml` added with a `dockerCommand` that rewrote the `DATABASE_URL` scheme with `sed` and then started `uv run uvicorn` (commit `524b2bc`). | `git log`, issue #12 |
| 14 Oct, 08:59 | The engineer's hand-off comment describes the local checks: the `sed` rewrite run alone, and the command string re-assembled and run with `sh -c`. | issue #12 comment |
| 14 Oct, 09:05 | QA passes the issue after its own simulation: the command was split into arguments and run through `subprocess` with a mocked `DATABASE_URL`. | issue #12 comment |
| 14 Oct, 09:06 | Issue #12 closed on QA PASS. Creating the Blueprint needed the owner's dashboard access and was left to the owner by design. | issue #12 comments |
| 14 Oct, before 09:19 | The first Render deploy runs and fails. The exact time of the Blueprint apply and of the crash is **not recorded**. | not recorded |
| 14 Oct, 09:19 | The owner reopens issue #12 with the dashboard log: `sh: 1: DATABASE_URL="<connection string>" uv run uvicorn app.main:app --host 0.0.0.0 --port 8100: not found`, then `==> Exited with status 127`. The connection string is left out here; it holds credentials. | issue #12 comment |
| 14 Oct, 09:26 | Fix committed: `406a48d` removes the `dockerCommand`; `5117c40` normalises `postgres://` and `postgresql://` to `postgresql+psycopg://` in `backend/app/config.py`, with 4 unit tests. The engineer builds and runs the real image against Postgres with no command override and gets a healthy `/health`. | git log, issue #12 comment |
| 14 Oct, 09:35 | QA repeats the real build and run independently and passes the fix. | issue #12 comment |
| 14 Oct, 09:36 | Issue #12 closed again. | issue #12 |
| 14 Oct, after 09:36 | Redeploy on Render left to the owner. The time of the first successful production deploy is **not recorded in the issue**. | issue #12 closing comment |

## Impact

- It was the first deploy of this service, so no earlier production version
  is recorded that users could have lost. No user report exists in the repo.
- The service did not start from the time of that first deploy until the
  fixed commit was redeployed. How long that was: **unknown / not recorded**
  (neither the crash time nor the redeploy time is in the repo).

## Root cause

- The `dockerCommand` value in `render.yaml` was a single string of the form
  `sh -c "DATABASE_URL=... uv run uvicorn ..."`. Render appears to have
  treated the whole string as the name of one executable, so `sh` reported it
  as "not found" and the container exited with 127 (the shell code for
  "command not found"). [`render.yaml` header comment; issue #12 fix comment]
- The reopening comment first read this as "`uv` is missing from the image".
  The fix pass showed that was wrong: `uv` is installed in the runtime stage
  and the Dockerfile's own `CMD` ran correctly with no override. The
  `render.yaml` header comment records the corrected reading. [issue #12]
- The exact way Render parses `dockerCommand` was **not investigated**: the
  chosen fix (do not override the command at all) removes the whole class of
  failure whatever the parsing rule is. [issue #12 fix comment]
- Contributing factor: the override existed only to rewrite the database URL
  scheme, a job the application can do itself once it accepts both forms.

## Detection

- Found by the owner, by reading the Render dashboard log after the first
  deploy, and reported in issue #12 at 09:19. [issue #12]
- Nothing automated detected it. The CI `deploy` job did not exist yet; it was
  added later that day (commit `d8e5494`, issue #13).

## Fix

- `406a48d`: `dockerCommand` removed from `render.yaml`. The Dockerfile's
  `CMD` is now the only thing that starts the container, exactly as in
  `docker-compose.yaml`.
- `5117c40`: `Settings` rewrites a bare `postgres://` or `postgresql://`
  `database_url` to `postgresql+psycopg://` (the driver the backend installs),
  covered by `backend/tests/test_config.py`.
- Verified by a real `docker build` and `docker run` against Postgres with a
  bare `postgresql://` URL, by the engineer and again by QA. [issue #12]

## Process change (what we do differently)

- **Verify with the entrypoint the platform uses.** The original checks
  exercised the command string in isolation (a `sed` run, an `sh -c` run, a
  `subprocess` simulation). None of them started the built image the way
  Render starts it, so the gap between "the string is correct" and "the
  platform runs it as a script" was never tested. The local simulation did not
  exercise Render's command handling; the later image run succeeded because
  the override was gone, not because it reproduced the failure.
  [`docs/ai-usage-report.md`, entries "Issue #12 reopened" and the closing
  reflection]
- **Do not override the container command** when the image's own `CMD` can do
  the job. `render.yaml` says so in its header comment.
- Real build-and-run against the actual deployment artifact is the standard
  for any issue that touches deployment, as the usage report records.
- The CI `deploy` job (issue #13) now polls `/health` for the expected
  commit, so a service that does not start is visible in the pipeline. The
  [runbook](../runbook.md) covers what to do when it does not.
- Related context (not a cause): QA's side finding in the #12 fix pass led to
  issue #17, which aligned the Python version and started the app from the
  baked virtual environment instead of `uv run`. [issue #17;
  `docs/ai-usage-report.md`]

## What we do not know

- The exact time of the first Render deploy and of the crash.
- How Render parses `dockerCommand`, and whether the same string would run
  under a different quoting. Not investigated.
- How long the service was down, and whether anyone tried to use it.
- Whether the Render log held other lines before the one reported. Only the
  lines pasted into issue #12 are available; the dashboard is owner-only.
