# Release process

Pinpoint deploys through GitHub Actions, not through Render's own
push-triggered deploys — see "Turning auto-deploy off" below for why.

## What triggers a deploy

Exactly one path: a push to `main` whose `backend`, `frontend`, and
`stack` jobs in `.github/workflows/ci.yml` all succeed. Once they do, the
new `deploy` job (`needs: [stack]`) calls Render's deploy hook and then
polls until the live service confirms it is serving that commit.

Three cases that look like they should deploy, but do not:

- **A pull request does not trigger a deploy**, even one that later
  merges into `main` — `deploy`'s `if:` condition
  (`github.event_name == 'push'`) never matches a `pull_request` event.
  Only the resulting merge commit landing on `main`, once *its own* CI run
  goes green, deploys.
- **A direct push to `main` whose `backend`, `frontend`, or `stack` job
  fails does not deploy** — `deploy` only starts once `stack` succeeds,
  and `stack` only starts once `backend` and `frontend` succeed
  (`needs: [backend, frontend]`). A failure anywhere in that chain means
  `deploy` never runs at all; it does not run and fail, it is skipped.
- **Nothing outside this workflow can trigger a deploy any more.**
  `render.yaml`'s `autoDeployTrigger: off` means a push alone, without a
  green CI run, does nothing on Render's side — Render will not start a
  deploy on its own just because `main` moved.

## Rollback

Two paths, covering a fast dashboard option and a slower, git-history-
preserving option.

1. **Render's own UI (fastest).** Open the `pinpoint` web service in the
   Render dashboard, go to its **Deploys** tab, find a previous deploy
   marked successful, and use that deploy's **Redeploy** action — the
   same mechanism already documented in `docs/deployment.md`'s
   "Rollback" section. This does not touch `main` or git history; it
   just makes Render serve an image it already built again.
2. **Revert and push through CI (slower, keeps history clean).**
   `git revert` the offending commit(s) (or push a fix) on `main`, and
   let `backend` → `frontend` → `stack` → `deploy` run green as normal —
   the same deploy hook fires and redeploys automatically. This pays for
   a full CI run, but keeps `main` and the deployed commit in sync and
   leaves a normal, reviewable git history. Prefer this path when there's
   time for a CI run; reach for the Render UI redeploy when there isn't.

## Turning auto-deploy off

This section describes the architecture this project already runs, not an
extra toggle a human flips separately. Before this release process was
introduced, `render.yaml` had no `autoDeploy`/`autoDeployTrigger` key at
all, and Render's documented default for an omitted field (`commit`)
meant Render auto-deployed on every push to the connected branch, by
itself, with no CI gate at all.

`render.yaml` now sets `autoDeployTrigger: off` on the `pinpoint` web
service. That is a real behavior change: Render itself never deploys on
a push any more. The **only** way a deploy happens is the CI `deploy`
job's explicit deploy-hook call, which only runs after a green `stack`
run on a direct push to `main` (see "What triggers a deploy" above). This
is deliberate — it means every deploy has already passed the full test
pipeline (`backend` + `frontend` + `stack`'s integration/e2e suites)
before Render ever builds the image for real traffic.

## How the smoke test works

After calling the deploy hook, the `deploy` job polls
`${{ vars.PUBLIC_URL }}/health` every 10 seconds for up to 10 minutes,
and only succeeds once the response's `commit` field matches the
triggering commit's SHA (`github.sha`) — a response from a stale,
previously-deployed commit is treated the same as "not yet deployed," not
as success. Ten minutes is a deliberate, generous budget: the deploy hook
call returns as soon as Render has *queued* the deploy, not when it's
live, and the actual wait is Render's own two-stage Docker build
(`npm ci` then `pip`/`uv sync`) plus a possible free-plan cold start
before the service serves its first request. `/health`'s `commit` field
is `null` outside a real Render deploy (local dev, Compose, CI's own
`stack` job) since there is no deployed commit to report there — see
`backend/app/config.py` and `backend/app/routers/health.py`.

## Failure hints in the `deploy` job

A red `deploy` job is not always our fault: on 14 Oct Render's own incident
blocked deploys and the hook answered HTTP 500 (see
`ops/incidents/2026-10-14-render-platform-outage.md`). So the job now says
where to look. When the deploy hook answers 5xx or cannot be reached, or when
`/health` never reports the commit within the 10-minute budget because it did
not answer or kept returning 5xx, the step prints a `HINT:` line naming
https://status.render.com and the decision tree in `ops/runbook.md`, and then
fails exactly as before. There is no hint for a 4xx from the hook (a bad or
rotated `RENDER_DEPLOY_HOOK_URL` is our configuration) or for a 4xx from
`/health`. When `/health` answers but with a different commit, the job prints a
`NOTE:` ("the service is up but serving a different commit") instead of the
outage hint. The hint is static text: the job does not query Render's status
API. Behaviour is unchanged otherwise: still 60 attempts, 10 seconds apart,
success only on a match. `ops/dry-run-deploy-hint.py` runs both steps against
local stubs to show each case.
