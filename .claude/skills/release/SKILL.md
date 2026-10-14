---
name: release
description: Walks a Pinpoint push to main through CI to a verified production deploy on Render, and names the two real rollback paths if the deploy job fails. Use this whenever the user wants to ship a change to production, is watching a deploy, or asks how to roll back a bad release.
---

Pinpoint deploys through exactly one path: a push to `main` whose CI jobs
all go green, after which the `deploy` job itself calls Render's deploy
hook and confirms the new commit is live. This skill is `docs/release-
process.md` and `.github/workflows/ci.yml` turned into steps — it invents
nothing beyond what those two files already do.

1. **Push to `main`.** Nothing deploys without this — not a pull request,
   and not a push whose `backend`, `frontend`, or `stack` job fails (see
   `docs/release-process.md`'s "What triggers a deploy").

2. **Watch the `CI` workflow.** Run `gh run watch` against the run
   triggered by that push (the workflow is literally named `CI` in
   `ci.yml`). Its real job order is `backend` and `frontend` running in
   parallel, then `stack` (`needs: [backend, frontend]`), then `deploy`
   (`needs: [stack]`). A failure anywhere before `deploy` means `deploy`
   is skipped, not run-and-failed.

3. **Once the run is green**, confirm the live service actually serves
   the new commit — the same check `deploy`'s own "Wait for /health to
   report this commit" step performs, done here by hand:

   ```
   curl -fsS "$PUBLIC_URL/health"
   ```

   Compare the response's `.commit` field against `git rev-parse HEAD`.
   They must match. A `null` or stale `.commit` means the deploy has not
   actually landed yet, even if the GitHub Actions run shows green.

4. **If the `deploy` job fails**, choose one of the two real rollback
   paths from `docs/release-process.md`'s "Rollback" section — do not
   invent a `render` CLI or a log-streaming command; neither exists for
   this setup:

   - **Render dashboard Redeploy (fast).** Open the `pinpoint` web
     service in the Render dashboard, go to its **Deploys** tab, find a
     previous deploy marked successful, and use that deploy's
     **Redeploy** action. This does not touch `main` or git history — it
     just makes Render serve an image it already built again. Reach for
     this when there is no time to wait on a full CI run.
   - **`git revert <sha>` and push through CI (slower, keeps history
     clean).** Revert the offending commit(s) on `main` and let
     `backend` → `frontend` → `stack` → `deploy` run green again; the
     same deploy hook fires automatically. This pays for a full CI run
     but keeps `main` and the deployed commit in sync with a normal,
     reviewable history. Prefer this path when there is time for a CI
     run.

This skill proposes these actions in words; it does not click Redeploy or
push a revert itself — see the `incident-response` skill and the
`on-call-responder` subagent for the same rule applied to an active
incident.
