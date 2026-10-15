# Runbook

Read this when production looks wrong: `/health` fails or looks odd, the CI
`deploy` job is red, or someone reports 5xx responses. It is written for an
operator who has never seen this repository. The question it answers is
**"is it our app, Render, or the database?"**, and the answer is in the
[decision tree](#decision-tree-is-it-our-app-render-or-the-database).

Who does what:

- **Agent** (Claude Code or another assistant): reads, diagnoses and
  proposes. It has no Render dashboard access (`docs/permissions.md`).
- **Owner** (the repository owner): the only person who can open the Render
  dashboard, read its Logs tab, press **Redeploy**, or change GitHub secrets
  and variables.

Related: [`docs/release-process.md`](../docs/release-process.md),
[`docs/deployment.md`](../docs/deployment.md),
[`ops/observability.md`](observability.md) (log line format),
[`ops/incidents/`](incidents/README.md) (past incidents),
[`ops/diagnosis-2026-10-15-cold-start.md`](diagnosis-2026-10-15-cold-start.md)
(measured cold-start time).

## Rules that always apply

- **Agents never call the Render deploy hook and never print
  `RENDER_DEPLOY_HOOK_URL`** (hook rule 5, `docs/permissions.md`). The hook is
  called by the CI `deploy` job and nowhere else.
- **Diagnosis from an agent is read-only: a plain `GET` of `/health`.** No
  login, no guest routes, no uploads, no `POST`.
- No code change and no retry loop before the provider has been ruled out
  (step 1 of the tree). A deploy that fails because Render is down is not
  fixed by editing code or by calling the hook again and again.
- No secret, connection string or token goes into an issue, a commit or a
  chat. Variable names only.

## Health check

- URL: `https://pinpoint-muou.onrender.com/health`
- Expected body: `{"status":"ok","commit":"<sha>"}` with HTTP 200, where
  `<sha>` is the 40-character commit Render built.
- `commit` is `null` outside a Render deploy (local run, Docker Compose, CI's
  own test jobs), because `RENDER_GIT_COMMIT` is only set by Render
  (`backend/app/config.py`, `backend/app/routers/health.py`).
- Compare it with what should be live:
  - `git fetch origin && git rev-parse origin/main` for the tip of `main`; or
  - the SHA of the CI run you are looking at (`gh run view <run-id> --json headSha`).

  If they differ, production is serving an older (or, after a rollback, a
  deliberately different) commit. Remember the `deploy` job only runs after a
  green `stack` job on a push to `main`, so a red run explains a stale commit
  without any Render problem (`docs/release-process.md`).
- Every response carries an `X-Request-Id` header
  (`curl -i .../health`); it is the handle for finding that request in the
  logs (`ops/observability.md`).

## Logs

- **Render (production):** the **Logs** tab of the `pinpoint` web service in
  the Render dashboard. Only the repository owner has dashboard access; no
  agent has it (`docs/permissions.md`). To get a log excerpt to an agent, the
  owner pastes it, after checking it holds no secret.
- **Docker Compose:** `docker compose logs app` (the web service is called
  `app` in `docker-compose.yaml`; the database is `postgres`).
- **Local, no Docker:** the terminal output of `make run`.
- Line format (JSON access log, request id): see
  [`ops/observability.md`](observability.md). Render's own health probe
  (`healthCheckPath: /health`) also shows up as requests in that log.

## Deploys and rollback

- How a deploy is triggered and verified, and why Render's own auto-deploy is
  off: [`docs/release-process.md`](../docs/release-process.md). Environment
  variables and the Blueprint: [`docs/deployment.md`](../docs/deployment.md).
  This runbook does not copy those procedures.
- Rollback path 1: in the Render dashboard, open the `pinpoint` service's
  **Deploys** tab and **Redeploy** a previous successful deploy (fast, owner
  only).
- Rollback path 2: `git revert` the offending commit and push to `main`, and
  let CI deploy it (slower, keeps `main` and production in step).
- Both are the owner's to run; an agent proposes the exact command or click.

## Database access

- Production uses a managed Postgres, `pinpoint-db` (database `pinpoint`,
  user `pinpoint`), created by the Blueprint in `render.yaml`. The app gets
  its connection string from the Blueprint (`DATABASE_URL`,
  `fromDatabase`); nobody types it in.
- The owner reaches the database from the Render dashboard (the `pinpoint-db`
  page). The dashboard shows an internal and an external connection string.
  The app's `DATABASE_URL` is Render's **internal** connection string
  (confirmed by the owner 2026-10-15; `render.yaml` sets `DATABASE_URL` with
  `fromDatabase`, `name: pinpoint-db`, `property: connectionString`). Which
  string works from the owner's own machine, and whether an IP allow-list is
  needed: **unconfirmed** (the owner did not answer this part). Never paste
  either string, or the password, into a file, an issue or a chat.
- The free Postgres **expires 30 days after creation** unless upgraded
  (`docs/deployment.md`, "Free plan limits"). It was created when the
  Blueprint was applied on 14 Oct 2026 (issue #12; exact time not recorded).
  Expiry is **about 13 Nov 2026, confirmed by the owner 2026-10-15** (written
  "about": the owner gave no exact date). An expired database looks like
  "`/health` fine, every other route 5xx" (tree, step 5). What to do before
  then: [Reminder: free database expires about 13 Nov 2026](#reminder-free-database-expires-about-13-nov-2026).
- The schema is created by the app on start (`Base.metadata.create_all`,
  `docs/deployment.md`, "No migration step"), so there is no migration to
  run by hand.

## Reminder: free database expires about 13 Nov 2026

Dated reminder, written 2026-10-15 (the free-plan limit is in
`docs/deployment.md`, "Free plan limits"; the date is the owner's, see
"Database access").

- **Before about 13 Nov 2026 the free Postgres (`pinpoint-db`) must be
  upgraded or recreated. Otherwise the live demo goes down:** the web service
  stays up and `/health` stays green, but every route that touches the
  database fails (decision tree, step 5).
- **Who acts: the owner, on the Render dashboard** (upgrade the plan, or
  recreate the database). Agents may only remind: they have no dashboard
  access (`docs/permissions.md`, "Needs the repo owner"). Nothing in this
  repository does either step, and `render.yaml` is not changed by this
  reminder.
- **What "recreated" implies.** A new database is empty. `docs/deployment.md`,
  "No migration step", and `backend/app/store/sqlalchemy/db_store.py`
  (`SQLAlchemyStore.__init__`) say the app creates the tables on every boot
  and runs the seed only when the database holds no studio user. So on the
  next boot of the web service the tables are created and the seed runs: the
  seeded demo data and the seeded demo login (the credentials in the root
  `README.md`, "Live demo") come back, and everything created on the live
  site since the seed (studio accounts, rooms, pins, comments, uploaded
  images, which are stored in the database) is lost.
- **Not confirmed, so not claimed:** whether Render keeps an expired free
  database for any grace period (the diagnosis,
  [`diagnosis-2026-10-15-cold-start.md`](diagnosis-2026-10-15-cold-start.md),
  quotes a figure from Render's free-plan page, but that page was read only
  through a summary, not verbatim); whether a recreated database is wired to
  the web service automatically or needs a manual step in the dashboard;
  whether an upgrade keeps the data and the connection string. The owner checks
  these on the dashboard.
- **How to tell afterwards that it worked.** `/health` does not touch the
  database, so it proves nothing here. The owner logs in to the live demo as
  the seeded studio and opens a seeded room.

## Free-plan behaviour

- The free web service **sleeps after about 15 minutes with no requests**.
  The next request is slow while the service starts again; a slow first
  request is **not an incident by itself**.
- The 15-minute figure comes from Render's documentation
  (https://render.com/docs/free), not from our own test; the page was read
  through a summary, not verbatim. The diagnosis only tested gaps of 16
  minutes. Of five attempts after such a gap, four were slow and one (`cold3`)
  was answered fast, so a cold start after 16 idle minutes is likely but not
  guaranteed, and nothing shorter than 16 minutes was tried.
- Measured wake-up time: **about 33 seconds** (4 of 5 attempts, `GET /health`,
  15 Oct 2026; 32.4 s to 32.8 s). Render's documented figure is about one
  minute (same page, same caveat). Details and the numbers behind them:
  [the diagnosis](diagnosis-2026-10-15-cold-start.md).
- Consequence for CI: the `deploy` job waits up to 10 minutes (60 x 10 s) for
  `/health` to report the new commit, which includes a possible wake-up.

## Decision tree: is it our app, Render, or the database?

Work top to bottom and stop at the first step that applies. "Agent" proposes;
"owner" acts on the dashboard or in GitHub settings.

1. **Check https://status.render.com first.** Look for an open incident on
   *builds*, *deploys* or *queued deploys*, or on the region of the service,
   and note its start time and any "free instances paused" line. Compare the
   start time with the time your symptom began.
   - **Open incident that matches: it is Render.** Do not change code, do not
     call the hook, do not loop retries. Record the incident title and start
     time, tell the owner, and **wait, then re-check when the status page says
     resolved**. After that, one re-run of the failed `deploy` job by the owner
     (or one push) is enough.
   - No open incident: continue with step 2.
2. **`GET /health`** (see "Health check"). What does it return?
   - **200 with the expected shape and the expected commit: production is fine.**
     If someone still reports a problem, ask for a time and an `X-Request-Id`
     and go to step 5.
   - **200 with the expected shape but an old `commit`:** go to step 3.
   - **No answer, timeout, 502 or 503:** go to step 4.
   - **200 but a different body, or a 4xx:** this is our app (wrong
     service, routing or a bad release). Agent proposes a rollback (path 1
     above); owner acts. Do not retry in a loop.
3. **`/health` answers with an old commit.** The new deploy has not gone live.
   - Is the CI run green through `deploy`? If `deploy` was skipped or red at an
     earlier job, that is a code or test failure, not Render: fix forward or
     revert via CI.
   - If `deploy` failed, go to step 6 (hook) or step 7 (wait loop).
   - If `deploy` is green but the commit is old, the owner checks the
     **Deploys** tab of the `pinpoint` service for a failed build or a
     deploy still in progress. Wait, then re-check `/health` when it shows
     live.
4. **`/health` times out or returns 502/503.** Cold start or outage?
   - If the service may have been idle for 15 minutes or more, this can be the
     wake-up. **Wait, then retry once** after about a minute: the measured
     cold start was about 33 s (4 of 5 attempts, 15 Oct 2026) and Render's
     documented figure, per Render's docs, is about one minute (see
     [the diagnosis](diagnosis-2026-10-15-cold-start.md)). Do not hammer the
     URL.
   - Still failing after that one retry and step 1 showed no incident: the owner
     opens the **Logs** and **Events** tabs of the `pinpoint` service. A crash
     at boot (for example the exit-127 case in
     [the 14 Oct postmortem](incidents/2026-10-14-render-deploy-exit-127.md))
     is our configuration. A suspended service or expired database is an
     account matter. Agent proposes a rollback only if the Logs show our code
     failing.
5. **`/health` is fine but other routes return 5xx.** The app is up, so it is
   our app or the database.
   - The owner reads the **Logs** tab around the failing time. Find the
     request by its `X-Request-Id` (`ops/observability.md`); the access log
     line has the route template and status, the traceback is in the normal
     error log next to it.
   - A database connection or "relation does not exist" error points at the
     database: the owner checks that `pinpoint-db` exists and has not
     expired (see "Database access"). A Python exception in our code points
     at the app: agent proposes a fix or a rollback; owner acts.
6. **`deploy` job fails at "Trigger Render deploy".** The step prints the
   response body; since #38 it also prints a `HINT:` line when the hook
   answered 5xx or did not answer at all.
   - **HTTP 5xx or unreachable:** this looks like Render. Go to step 1. If an
     incident is open, wait and re-run the job later (owner). **Do not** edit
     code and **do not** re-run in a loop.
   - **HTTP 4xx (no hint):** our configuration: the `RENDER_DEPLOY_HOOK_URL`
     secret is wrong or was rotated. Owner checks the secret in GitHub; agent
     never reads or prints it.
7. **`deploy` job fails at "Wait for /health to report this commit".** After
   10 minutes `/health` did not report this commit.
   - Final message says the service **never answered or kept returning
     5xx** (with a `HINT:` line): go to step 1, then step 4.
   - Final message says the service **is up but serving a different
     commit:** the hook worked but the new deploy did not go live, or a newer
     commit is already live (a re-run of an older run compares against its own
     SHA). Go to step 3; owner checks the **Deploys** tab.
   - Final message says `/health` returned a 4xx: our app or routing; go to
     step 2.

Every leaf above ends in an action for the owner or a condition to wait for.
If none of them fits, write down what you saw (time, status, `X-Request-Id`,
the `commit` value) and ask the owner for the Logs excerpt; do not guess.

## Writing it down

After a real incident, add a blameless entry to
[`ops/incidents/`](incidents/README.md). Past entries:

- [2026-10-14, Render deploy exit 127](incidents/2026-10-14-render-deploy-exit-127.md)
- [2026-10-14, Render platform outage](incidents/2026-10-14-render-platform-outage.md)
