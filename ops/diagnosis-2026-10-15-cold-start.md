# Diagnosis: production cold start, 15 Oct 2026

Measured wake-up time of the `pinpoint` web service on Render's free plan,
taken for issue #38 (part 4). The measurements and the local capture are in
this file. The analysis and the recommendation at the end were written
afterwards by the `on-call-responder` agent from the numbers above and are
included unedited. Where to look when production misbehaves:
[`runbook.md`](runbook.md).

## Scope and method

- **Only `GET https://pinpoint-muou.onrender.com/health`.** No other route, no
  `POST`, no login, no guest route, no upload, and the Render deploy hook was
  never called (see "Read-only statement" at the end).
- **Served commit** is read from the `commit` field of the response body. It
  was `c32f839` on every sample, so every number here describes the build that
  contains the JSON access-log middleware (issue #38, part 5;
  [`observability.md`](observability.md)). It does not describe any earlier
  build.
- **Timings** are curl's `-w` variables in seconds: `time_namelookup`,
  `time_connect`, `time_appconnect`, `time_starttransfer`, `time_total`. Every
  sample returned HTTP 200.
- **Warm samples (n=5):** taken while the service was awake, 6 to 7 seconds
  apart. The service was awake because the `deploy` job of CI run 38697503500
  (green) had polled `/health` during the deploy, and because one more `GET`
  of `/health` (HTTP 200, commit `c32f839`) by the orchestrator at about 07:19
  UTC preceded `warm1`.
- **Cold attempts (up to 5):** each attempt follows a sleep of 960 seconds
  (16 minutes) in the sampler, with no request from us in between. The idle gap
  in the table is the time since our previous request; `cold1`'s gap runs from
  the end of `warm5`. Because the gap is the sampler's own sleep, the true gap
  can differ by a second or two.
- **Cold threshold, fixed before any cold result:** an attempt counts as cold
  only if the idle gap is at least 15 minutes **and** `time_total` is greater
  than 1.0 s. The warm totals are all below 0.281 s.
- **Count: 4 of 5 cold samples.** `cold3` met the gap but its `time_total` was
  0.284 s, inside the warm range, so it is listed as "gap met, not observed
  cold" and excluded from the cold count and from the cold statistics. It is
  not hidden and not replaced. Conclusions about cold-start time rest on these
  4 samples.
- **Statistics:** minimum, median and maximum per group with the sample count,
  and the numbers behind them. No percentiles: 4 and 5 samples do not support
  them. For the cold group (n=4) the median is the mean of the two middle
  values.
- **Sources of context.** The 07:20 to 08:42 UTC window is described by the
  operator of the sampler: nothing else of ours touched the service in that
  window. That is not independently verifiable beyond the operator's
  statement.

## Raw measurements

### Warm (n=5, service awake)

| # | Start (UTC) | Status | Commit | namelookup | connect | appconnect | starttransfer | total |
|---|---|---|---|---|---|---|---|---|
| warm1 | 2026-10-15T07:19:37.549Z | 200 | c32f839 | 0.022884 | 0.030393 | 0.048126 | 0.275492 | 0.275938 |
| warm2 | 2026-10-15T07:19:43.871Z | 200 | c32f839 | 0.024558 | 0.031343 | 0.046510 | 0.275008 | 0.275401 |
| warm3 | 2026-10-15T07:19:50.176Z | 200 | c32f839 | 0.019001 | 0.026665 | 0.049192 | 0.280460 | 0.280836 |
| warm4 | 2026-10-15T07:19:56.495Z | 200 | c32f839 | 0.017778 | 0.025388 | 0.047058 | 0.279759 | 0.280114 |
| warm5 | 2026-10-15T07:20:02.803Z | 200 | c32f839 | 0.025639 | 0.032276 | 0.052240 | 0.277781 | 0.278083 |

| Warm, n=5 | min | median | max |
|---|---|---|---|
| time_starttransfer (s) | 0.275 | 0.278 | 0.280 |
| time_total (s) | 0.275 | 0.278 | 0.281 |

### Cold attempts

| # | Start (UTC) | Idle gap since our previous request | Status | Commit | namelookup | connect | appconnect | starttransfer | total | Counted |
|---|---|---|---|---|---|---|---|---|---|---|
| cold1 | 2026-10-15T07:36:08.462Z | 16 min 05.4 s (965.4 s) | 200 | c32f839 | 0.029221 | 0.036572 | 0.073813 | 32.382870 | 32.383325 | COLD |
| cold2 | 2026-10-15T07:52:40.934Z | 16 min 00.0 s (960.0 s) | 200 | c32f839 | 0.060046 | 0.066696 | 0.089511 | 32.395274 | 32.395754 | COLD |
| cold3 | 2026-10-15T08:09:13.367Z | 16 min 00.0 s (960.0 s) | 200 | c32f839 | 0.029417 | 0.036051 | 0.056031 | 0.283632 | 0.284091 | gap met, NOT observed cold (excluded from the cold count) |
| cold4 | 2026-10-15T08:25:13.678Z | 16 min 00.0 s (960.0 s) | 200 | c32f839 | 0.026611 | 0.033968 | 0.054450 | 32.373140 | 32.373559 | COLD |
| cold5 | 2026-10-15T08:41:46.080Z | 16 min 00.0 s (960.0 s) | 200 | c32f839 | 0.253919 | 0.261485 | 0.481789 | 32.763738 | 32.764144 | COLD |

| Counted cold, n=4 (cold1, cold2, cold4, cold5) | min | median | max |
|---|---|---|---|
| time_starttransfer (s) | 32.373 | 32.389 | 32.764 |
| time_total (s) | 32.374 | 32.390 | 32.764 |

What the table shows, and nothing more:

- In the four counted cold samples the time is in time to first byte
  (`time_starttransfer`). DNS, connect and TLS are small: `time_appconnect` is
  at most 0.482 s in any sample.
- Cold1, cold2, cold4 and cold5 land near 32.4 s (cold5 at 32.76 s). That is
  observed. No cause is asserted here.
- Cold3 had the same gap as cold2, cold4 and cold5 and was answered in
  0.284 s. **Why is unknown.** Traffic to the service that we did not generate,
  a platform probe, and a spin-down that did not happen are all possible, and
  none of them is established. It is one attempt out of five and is reported
  as it came.

## Startup log sequence

**Render's startup log was not observed by this diagnosis.** Agents have no
access to the Render dashboard ([`../docs/permissions.md`](../docs/permissions.md)),
so nothing below is a Render log line. The first part is derived from the code;
the second part is a capture from a local container, labelled as such.

### Expected sequence, derived from the code

1. **Process.** `Dockerfile` line 61:
   `CMD ["/app/backend/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]`,
   with `WORKDIR /app/backend` (line 59). The command starts the virtualenv's
   `uvicorn` directly; `uv` is installed in the image (line 37) and runs
   `uv sync --frozen --no-dev` at build time (line 42), but is not part of the
   start command.
2. **Import of `app.main`** (uvicorn imports the application before it serves).
   There is no FastAPI `lifespan` and no `on_event("startup")` hook anywhere in
   `backend/app` (searched for `lifespan`, `on_event`, `startup`). All startup
   work therefore happens at import time:
   - `backend/app/config.py:87` builds `settings`. With
     `ENVIRONMENT=production` and the default `JWT_SECRET` this raises
     (`config.py` model validator), so a missing secret fails at import.
     `DATABASE_URL` is rewritten from `postgres://` or `postgresql://` to
     `postgresql+psycopg://` in the same class.
   - `backend/app/store/__init__.py:18`:
     `_store = SQLAlchemyStore(settings.database_url)`. This runs when the
     module is first imported (through `app.routers`, `app.auth`).
   - Importing `backend/app/store/sqlalchemy/db_store.py` runs line 41,
     `_DEMO_PASSWORD_HASH = hash_password(seed.DEMO_PASSWORD)`: one bcrypt hash
     at import time.
   - `SQLAlchemyStore.__init__` (`db_store.py:102`) calls
     `Base.metadata.create_all(...)` (line 105), which opens a connection to
     the database and creates missing tables, then checks for a user row
     (line 116) and runs `_seed()` (line 118) only on an empty database.
     A database that cannot be reached fails here, at import, and uvicorn
     exits before it serves anything.
   - `backend/app/main.py:20` calls `install_access_log(app)`, which disables
     `uvicorn.access` (`backend/app/access_log.py:173`) and wraps the built
     middleware stack (lines 175 to 180).
3. **uvicorn's own lines** (stderr, default format): `Started server process`,
   `Waiting for application startup.`, `Application startup complete.` (the
   lifespan handshake succeeds trivially, since the app defines no lifespan),
   `Uvicorn running on http://0.0.0.0:8100 (Press CTRL+C to quit)`.
4. **Per request.** One JSON line on stdout per request, from
   `backend/app/access_log.py`: `ts`, `level`, `request_id`, `method`, `path`
   (the route template, or `unmatched`), `status`, `duration_ms`. uvicorn's
   own access log is disabled, so there is no second line per request. Format:
   [`observability.md`](observability.md).

### What the issue #17 change does at startup

Issue #17 (commit `ec6f564`; entry "Issue #17" in
[`../docs/ai-usage-report.md`](../docs/ai-usage-report.md)) aligned the
interpreter pin with the image's Python 3.12 and changed `CMD` from
`uv run uvicorn ...` to the venv's `uvicorn` binary. Before it, the start
command went through `uv run`, which checks the environment against the
project on every start. After it, `uv` is not run at container start; the
local capture below shows no `uv` output. That is a statement about this image
and the local start. What Render does around the container (pull, spin-up,
probes) is not part of that change and is not observed.

### Local capture, LOCAL, not Render

**LOCAL, not Render.** This is not a Render log and says nothing about what
Render printed.

Method: `docker build -t pinpoint-local-diag .` from the working tree at
`c32f839` (clean tree), then a throwaway `postgres:16-alpine` and the image on
a private Docker network, published only on `127.0.0.1`. Environment values:
the placeholders from `.env.example` and `ENVIRONMENT=development`;
`DATABASE_URL=<redacted: bare postgresql:// URL to the throwaway container>`,
`JWT_SECRET=<redacted: the .env.example placeholder>`. No `.env` and no
`_local/` was mounted or read. Containers, network and image were removed
afterwards. Machine: Windows 11 with Docker Desktop, Docker 28.1.1; times
below are from that machine, not from Render.

`docker logs -t` from the first start (empty database) to the first local 200
on `/health`, in full:

```
2026-10-15T08:44:39.636246658Z INFO:     Started server process [1]
2026-10-15T08:44:39.636288039Z INFO:     Waiting for application startup.
2026-10-15T08:44:39.638561514Z INFO:     Application startup complete.
2026-10-15T08:44:39.639638246Z INFO:     Uvicorn running on http://0.0.0.0:8100 (Press CTRL+C to quit)
2026-10-15T08:44:39.852338514Z {"ts":"2026-10-15T08:44:39.851Z","level":"INFO","request_id":"39b2989886524fc39813197d2e0b938d","method":"GET","path":"/health","status":200,"duration_ms":71.119}
```

The container reported `StartedAt` 08:44:35.467Z. The local `/health` body was
`{"status":"ok","commit":null}` (`commit` is `null` outside a Render deploy).

| Local observation (LOCAL, not Render) | Value |
|---|---|
| Container start to first uvicorn line, first start, empty database (tables created and seeded) | 4.17 s |
| Container start to first `/health` 200 log line, same start | 4.39 s |
| Restart of the same container, database already seeded, 3 samples, start to first uvicorn line | 1.27 s, 1.41 s, 0.97 s |
| Restart of the same container, first sample, start to first `/health` 200 log line | 1.46 s |
| Restart after dropping the schema (tables created and seeded again), start to first uvicorn line | 1.24 s |
| Newly created container against a seeded database, 3 samples, start to first uvicorn line | 2.46 s, 2.03 s, 2.12 s |
| PID 1 | `/app/backend/.venv/bin/python /app/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8100` |
| Python in the venv | 3.12.15 |
| PID 1 resident memory after start (local) | about 97 MB (`VmRSS` 97376 kB) |
| `uv` output in the container log | none |

Notes on these numbers:

- They are single local runs, not a benchmark. The first start was slower than
  every later start (4.17 s against 0.97 to 2.46 s). What made it slower is not
  established: it was a first start of a new container on an empty database,
  but the restart after dropping the schema (also an empty database) took
  1.24 s, so the empty database alone does not explain it.
- Importing `app.config`, `app.auth` (which imports the store) and `app.main`
  in a fresh container took 0.53 s, 1.24 s and 0.08 s, 1.85 s in total, against
  an already seeded database. This is most of the local start time; it was not
  broken down further.
- A previous engineer reported about 4.1 s from `docker run` to the first
  uvicorn line, about 4.35 s to the first local 200, about 1.8 s for a restart
  on a seeded database, PID 1 as above on Python 3.12.15, and no `uv` output.
  This capture agrees on the first start (4.17 s and 4.39 s), on PID 1, on the
  Python version and on the absence of `uv` output. For the restart it measured
  1.0 to 1.5 s rather than 1.8 s; the two may have measured to different
  endpoints.
- Nothing in the capture is a Render number. It is the application's own start
  on a developer machine and is not compared with the 32 s here; that
  comparison belongs to the analysis.

### What could not be observed on Render

- Image pull and spin-up time of the instance before our container starts.
- Platform health-check probes. `render.yaml` sets `healthCheckPath: /health`
  (line 34); what Render does with it, and when, was not observed.
- The actual log lines Render prints for a cold start, and their timestamps.
- Memory use of the instance.
- Whether the sleeping instance is a new container or a resumed one.

The owner has dashboard access and can close this gap: paste the **Logs** tab
of the `pinpoint` service covering one cold start (a request after at least 15
minutes of silence) into the issue or this file, with the time of the request.
Before posting, check the paste for secrets; the access log does not contain
any (see [`observability.md`](observability.md)), but platform lines might.

## Defects found

**No defect found.** Nothing in the measurements or in the local capture looked
broken:

- Startup: no error, no traceback, no restart loop in the local capture. All
  four uvicorn lines are present in the expected order.
- Health probe: `/health` answered HTTP 200 with `status: "ok"` on all ten
  sampled production requests and on every local request; every production sample
  served commit `c32f839`. The slowest production answer was a successful 200.
- Port: the container listens on 8100 as the `Dockerfile` says
  (`Uvicorn running on http://0.0.0.0:8100`). What port Render routes to was
  not observed.
- Access log: one JSON line per request, with a request id on the matching
  `X-Request-Id` response header (checked locally), `path` as the route
  template (`/health`), and `unmatched` for an unknown path. No duplicate
  uvicorn access line.

This matches the previous engineer's finding of nothing broken. No code change
follows from this diagnosis.

## CI wait loop

Arithmetic only, from `.github/workflows/ci.yml` (`deploy` job, step "Wait
for /health to report this commit", lines 293 and 294):

- The loop makes up to 60 attempts, with a 10 s `sleep` after a failed attempt:
  60 x 10 s = 600 s of sleeping, which the log message reports as "Timed out
  after 600 seconds".
- The `curl` in each attempt has no `--max-time` (line 300), so an attempt
  lasts as long as the response takes. The wall time of the loop is the
  sleeping plus the time spent in requests.
- One wake-up of 32.4 s to 32.8 s (the counted cold samples) is 5.4 % to 5.5 %
  of the 600 s of nominal sleep budget, and it would occupy about three
  10-second poll intervals (32.8 / 10 = 3.3). It fits inside the budget with
  about 567 s left.
- In the CI deploy each poll is itself a `GET /health` request to the
  service, so the polling is traffic that wakes a sleeping service. The first
  poll that reaches a sleeping service is the one that waits for the wake-up.
- How long the build and the switch to the new commit take was not measured
  here, so this section gives the wake-up's share of the budget only, not the
  whole deploy's.

## Analysis

*Sources: ops/diagnosis-2026-10-15-cold-start.md (all), docs/deployment.md, docs/release-process.md, ops/runbook.md, render.yaml, README.md (lines 29-32), _docs/decisions.md (Deployment row, line 18); URLs read: https://render.com/docs/free (fetched; summarised by a fetch tool, not read verbatim). Fetched but containing no prices or instance specs: https://render.com/pricing, https://render.com/pricing#compute, https://render.com/docs/web-services. HTTP 404: https://render.com/docs/instance-types, https://render.com/docs/pricing. I did not open the Dockerfile or ci.yml myself; I rely on the report's quotes of them. This is advice from the on-call-responder agent, not authority.*

Written by the on-call-responder agent from the numbers above; not edited by the engineer. Advice only: no change to render.yaml or the Deployment decision.

**Cold-start cost.** In the 4 counted cold samples (cold1, cold2, cold4, cold5) `time_total` was 32.374 s min, 32.390 s median, 32.764 s max. The 5 warm samples were 0.275 s min, 0.278 s median, 0.281 s max. On the same request (`GET /health`), 32.39 / 0.278 is about 116, so roughly 115x. The report states no percentiles, and neither do I. Nearly all of the time is in `time_starttransfer` (32.373 to 32.764 s). DNS, connect and TLS are small: `time_appconnect` is at most 0.482 s (cold5) and 0.074 to 0.090 s in the other three. Cold1, cold2 and cold4 are within 0.022 s of each other (32.373 to 32.395 s). Cold5 is 0.37 s higher, with a slower lookup and connect (0.254 s and 0.261 s). That regularity is observed. I do not assert a cause for it.

**Cold3.** It had the same 16-minute gap, but `time_total` was 0.284 s, just above the warm maximum of 0.281 s and inside the warm range. It shows that spin-down was not guaranteed after a 16-minute gap on this service: 4 of 5 attempts were cold, and 1 was not. It does not show why. The report names three possibilities: traffic we did not generate, a platform probe, or a spin-down that did not happen. None is established, and I add no others. One attempt cannot give a rate of spin-down.

**Consistency with the documents.**
- docs/deployment.md only says the first request after idling "pays a cold-start delay". The numbers fit that, but the doc gives no figure.
- README's "roughly 30-60 seconds": 32.4 to 32.8 s is inside that range, at its low end.
- Render's free-plan page says a service spins down after "15 minutes without receiving any inbound traffic" and that spin-up "takes about one minute" (https://render.com/docs/free). The measurements are consistent with both statements.
- The runbook's "about 15 minutes" idle claim is not tested at its edge. All gaps were 16 minutes (one was 16 min 05.4 s). We tried no shorter gap, so we know nothing about 5, 10 or 14 minutes.

**Is anything broken?** No defect was found. The 32 s is not explained by the application's own start. The local first start took about 4.2 s to the first uvicorn line and 4.4 s to the first 200, and the seeded restarts took 1.0 to 2.5 s. This is a developer machine, not Render, so the comparison is loose. Even so, roughly 28 s of the 32.4 s is not accounted for by the app's startup. What makes up that remainder on Render was not observed, because the Render dashboard log was not seen. I do not guess the split. The report lists what is unobserved: image pull and spin-up before our container starts, platform probes, Render's log lines, and whether the instance is new or resumed.

**Effect on CI and people.**
- The CI wait loop is 60 x 10 s of sleep. One wake-up of 32.4 to 32.8 s is about 5.5 % of that budget, or about 3 poll intervals, so it fits. The `curl` has no `--max-time`, so a poll waits as long as the response takes. Here it waited about 33 s and got a 200.
- A client with a timeout under about 33 s would have seen a failure on the same request. That is arithmetic, not observed.
- A person opening the site would wait about half a minute for the first response. Render says browsers see "a loading page" in the meantime (https://render.com/docs/free). I did not observe what our site shows.
- The runbook's "wait, then retry once" is sound. The measured wait is about 33 s, and Render's own figure is about a minute. A retry after roughly a minute covers both.

**Limits.** 4 cold samples, with one more attempt that was not cold. One URL (`/health`, a light route). One time window (07:19 to 08:42 UTC), one region, one day, and one build (`c32f839`). No gap under 16 minutes was tried. The "nothing else touched the service" statement is the sampler operator's own and cannot be checked.

## Recommendation

The brief for the recommendation was to pick exactly one of: (1) keep the
free plan and document the wake-up in the runbook, (2) add an external uptime
ping, (3) move to a paid instance. It is advice only: this issue does not add a
ping, does not change the plan and does not touch `render.yaml` or the
Deployment row of `_docs/decisions.md`; that is the owner's decision.

**Choose option (1): keep the free plan and document the wake-up.** This is advice only. It changes nothing in `render.yaml` and does not reopen the Deployment row of `_docs/decisions.md`.

**Reasons from the data.**
- All four cold requests completed with HTTP 200 in at most 32.8 s, inside the documented range.
- Nothing was found broken.
- The CI loop absorbs a wake-up with about 567 s to spare.
- The cost is one slow first request after idle, which the project accepted when it chose the free plan (docs/deployment.md, "Free plan limits").

**Options not chosen.**
- (2) External ping:
  - Render counts inbound traffic as what keeps a free service awake (https://render.com/docs/free). A ping more often than every 15 minutes would therefore defeat the idle spin-down.
  - The same page grants 750 free instance hours per workspace per calendar month, and an always-awake service uses about 744 h in a 31-day month (my arithmetic). That is tight if the workspace has any other free service.
  - The page says nothing for or against pings, and I found no acceptable-use text. Whether a ping conflicts with Render's terms is unconfirmed, because I did not read the terms.
  - The same page says free instances should not be used for production and that Render "might restart a Free web service at any time". A ping would not prevent a restart.
  - A ping also adds an external dependency and extra access-log lines.
- (3) Paid instance: I could not read any instance price or spec from Render's public pages, so I state no price. Whether a paid instance never spins down is also unconfirmed here. A paid web service needs billing on the account. It would not fix the database: free Postgres "expire[s] 30 days after creation" and is deleted after a 14-day grace period (https://render.com/docs/free). The runbook estimates expiry around 13 Nov 2026, which is a more pressing dated item than the 32 s.

**What would change this advice.**
- Moving toward (3):
  - Real clients or reviewers start using the live URL and hit client timeouts or abandon it.
  - A wake-up longer than about 60 s.
  - The `deploy` job failing because of a wake-up.
- Moving toward (2): an owner-confirmed read of Render's terms that allows pings, plus a decision that a half-minute first load matters.
- Fixing the app rather than the plan: Render logs showing that part of the remainder is our own startup or image.

**Follow-ups for the owner.**
- README lines 29 to 32: replace "roughly 30-60 seconds" with the measured "about 33 seconds (4 of 5 attempts, 15 Oct 2026)". Keep Render's "about one minute" as the documented figure.
- ops/runbook.md:
  - Line 107: say the 15-minute figure comes from Render's docs, and that we tested only 16-minute gaps.
  - Lines 110-111 and 150-151: replace "pending measurement" with about 33 s, and keep "wait, then retry once" with a wait of about a minute.
  - Add one line that a cold request can be answered (cold3) or not.
- docs/deployment.md lines 85 to 87: link the diagnosis and add the measured figure.
- Separately, the owner may want `--max-time` on the CI `curl` (line 300), which is their decision.
- Measure next:
  1. The owner pastes the dashboard Logs tab covering one cold start, with the time of the request. This closes the unobserved 28 s.
  2. Gaps of 5, 10, 14 and 15 minutes, to test the 15-minute claim.
  3. A repeat at other times and on other days, and a second look at cold3-type misses.
  4. The duration of a full deploy, which this report did not measure.

## Read-only statement

Only `GET /health` was requested from production, by this measurement and by
the single earlier request noted above. The Render deploy hook was never
called, and `RENDER_DEPLOY_HOOK_URL` was never read or printed. No login, guest
route, upload or any other production route was requested. The local capture
used no production credential and no `.env` file.
