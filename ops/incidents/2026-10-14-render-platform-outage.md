# 2026-10-14: deploys blocked by a Render platform incident

Blameless postmortem. Actors are roles and systems ("the deploy job", "the
agent", "the owner"); no person is named. Every time is UTC. Sources are in
brackets; the CI times come from `gh run view <run-id> --json jobs`. Where the
repo does not record something it says so.

Related: [runbook, decision tree](../runbook.md) ·
[the exit-127 incident the same day](2026-10-14-render-deploy-exit-127.md)
(a different cause: our configuration, not the provider).

## Summary

On 14 Oct the CI `deploy` job failed at "Trigger Render deploy" on three
consecutive pushes because the deploy hook answered HTTP 500 (`curl` exit 22).
status.render.com listed a Render incident, "Builds, deploys, and queued
deploys are not starting in all regions", on 14 Oct 19:32-22:18 UTC, with
deploys for free instances paused from 20:41 UTC. The owner re-ran the
`deploy` job on 15 Oct at 06:38 UTC, the hook step succeeded, and production
then served `51dfe85`. The cause of the failed deploys was Render's incident.
Our own gap was how the first failure was handled: it was labelled transient
without opening the provider status page first.

## Timeline

CI times are the start and end of the "Trigger Render deploy" step of the
`deploy` job in each run attempt.

| Time (UTC) | Event | Source |
|---|---|---|
| 14 Oct 19:28 | Run 38623992537 starts (push `88d9dd7`). | `gh run view` |
| 14 Oct 19:30:51-19:30:57 | Attempt 1, hook step fails (`curl: (22)`, HTTP 500). | `gh run view`; usage report |
| 14 Oct 19:31:27-19:31:33 | Attempt 2 (a re-run of the job), hook step fails the same way. | `gh run view`; usage report |
| 14 Oct, about 19:31 onward | Live `/health` returns 502 on each of four checks over about two minutes. Exact times **not recorded**. | usage report |
| 14 Oct 19:32 | status.render.com lists the incident (start time as listed). The two hook failures above are less than two minutes before that listing (the page lists minutes only). | status.render.com |
| 14 Oct 19:38 and 19:44 | Pushes `d139943` and `cd03812`: the hook step succeeds and `/health` reports the new commit (runs 38625084774 and 38625797747). The first failure is then logged as "a transient Render-side condition that cleared by itself". | `gh run view`; usage report |
| 14 Oct 20:41 | status.render.com: deploys for free instances paused. The page states no resume time. | status.render.com |
| 14 Oct 20:46 | Run 38634842001 starts (push `dc67e2c`). | `gh run view` |
| 14 Oct 20:48:29-20:48:30 | Attempt 1, hook step fails (HTTP 500, within about half a second). | `gh run view`; usage report |
| 14 Oct 20:56:46 | Attempt 2, hook step fails. | `gh run view` |
| 14 Oct, after 20:48, times not recorded | Live `/health` does not answer: six 45-second attempts over about six minutes, then a seventh. | usage report |
| 14 Oct 20:58 | Run 38636571123 starts (push `cf08ee7`); hook step fails 21:00:46-21:00:47 (HTTP 500). | `gh run view`; usage report |
| 14 Oct, time not recorded | The owner reports a Render incident; the hook is not retried and polling stops on the owner's instruction. The usage report is updated to say the failure is Render's. | usage report |
| 14 Oct 22:18 | status.render.com lists the incident as resolved. | status.render.com |
| 15 Oct 06:38:33 | The owner re-runs the `deploy` job of run 38634842001 (attempt 3). Hook step succeeds (06:38:34-06:38:35). | `gh run view` |
| 15 Oct 06:38:35-06:42:31 | "Wait for /health" step runs, then is **cancelled** at 06:42:31; the run's conclusion is `cancelled`. By whom or why is **not recorded** in the run data. | `gh run view` |
| 15 Oct | Production serves `51dfe85` (reported to the engineer by the orchestrator; to be re-checked by a `GET /health` in the live diagnosis, part 4 of issue #38). | orchestrator hand-off |

## Impact

- Pushes `88d9dd7` (first failure), `dc67e2c` and `cf08ee7` did not deploy
  when pushed. The four application fixes of issue #26 (in `dc67e2c`) stayed
  unverified in production until the 15 Oct re-run. [usage report]
- The live service did not answer `/health` during the observations above.
  Whether the site was unusable for users, and for how long, is **unknown**:
  no user report exists in the repo and the observations have no end time.
- Nothing else is recorded as lost: no data change, no wrong code live.

## Root cause

- **Render's incident (not ours).** The hook returned HTTP 500 while
  status.render.com listed an incident on builds and deploys, and while free
  instance deploys were paused (from 20:41). The failures in runs 38634842001
  (20:48, 20:56) and 38636571123 (21:00) fall inside that window and inside the
  pause. After the incident was marked resolved the hook step succeeded
  (15 Oct 06:38). This is consistent with the provider being the cause. We
  did not observe Render's side directly (no dashboard access).
- **The first failure (run 38623992537, 19:30 to 19:31).** It falls less than two
  minutes before the incident was listed, and two later hooks at 19:38 and
  19:44 succeeded inside the listed window. So the status page lists an
  incident that started around then, but whether that first failure belongs to
  it is **unknown / consistent with**, not established.
- **The `/health` timeouts and 502s** were observed, not explained. They are
  consistent with the same incident (and with the free-plan wake-up, see the
  [runbook](../runbook.md)); no source ties them to either. Cause: **unknown**.

## Detection

- The failed `deploy` job was visible on each run. The first run's failure was
  noticed by the orchestrator when recording the CI result; the provider
  incident was identified when the owner reported it from the status page.
  [usage report]
- Nothing in the job pointed at the provider: the log said `curl: (22)` and the
  response body, with no hint about where to look.

## Fix

- No code fix applies; the cause was external. The deploy was completed by
  re-running the failed `deploy` job after the incident was resolved
  (owner, 15 Oct 06:38).
- Process fixes follow below.

## Process change (what we do differently)

Separating the two things:

- **Render's incident:** not ours, nothing to change in the application.
- **Our process gap:** the first failure was labelled transient because the
  next push passed, without opening status.render.com. Two re-runs of the job
  were made (attempt 2 of both runs) and `/health` was polled before the
  provider was ruled out, and a deploy-job change was considered; issue #38's
  grooming records this, `docs/ai-usage-report.md` does not say what was
  proposed. A 500 from the hook, which fails before Render builds anything, is
  treated from now on as a possible provider symptom first.

What we do now:

1. **Check the provider first.** Step 1 of the
   [runbook decision tree](../runbook.md#decision-tree-is-it-our-app-render-or-the-database)
   is status.render.com, and it says no code change and no retry loop before
   the provider is ruled out.
2. **The `deploy` job points there.** When the hook answers 5xx or does not
   answer, or `/health` never answers within the budget, the job prints a
   `HINT:` naming status.render.com and the runbook (issue #38, part 3,
   `.github/workflows/ci.yml`; `docs/release-process.md`). It prints no hint
   for a 4xx, which is our configuration.
3. **Do not label a failure transient** until the status page has been checked
   and the check is written in the log entry.
4. **Re-running an old run's `deploy` job** compares `/health` with that run's
   own SHA. The 15 Oct re-run waited for `dc67e2c` while production served
   `51dfe85`, a later commit, so it could not have matched. The job's final
   message now says "service is up but serving a different commit" for that
   case.

## What we do not know

- Whether the three hook failures were all caused by Render's incident. The
  provider status was not observed by us during the failures; the first one
  precedes the status listing.
- What the hook returned in the body each time beyond HTTP 500.
- Why the "Wait for /health" step of the 15 Oct attempt was cancelled, and by
  whom.
- Whether Render's hook always deploys the tip of `main` rather than the commit
  of the run that calls it. Production serving `51dfe85` is consistent with
  that; it is not verified.
- When free-instance deploys resumed: the status page states no resume time.
- The times of the `/health` timeouts and the owner's report.
- How long users were affected, if at all.
