---
name: incident-response
description: Diagnoses a live Pinpoint production problem — /health looking wrong, 5xx reports, a suspicious deploy — decides rollback vs. fix-forward, and writes the incident up in ops/incidents/. Use this whenever the user reports production is down, misbehaving, or asks "what's wrong with prod" / "do we need to roll back".
---

This is the same diagnosis this project's `on-call-responder` subagent
performs, written as a checklist anyone (or that subagent) can follow. It
never invents a command or log-access mechanism this repo does not
already have.

1. **Check `/health`.**

   ```
   curl -fsS "$PUBLIC_URL/health"
   ```

   Compare the shape against `backend/app/routers/health.py`'s expected
   `{"status": "ok", "commit": ...}` response. A missing field, a 5xx, or
   a response that does not come back at all is itself a finding.

2. **Read the Render dashboard Logs tab by hand.** There is no CLI access
   to Render logs or metrics from this repo — no Render CLI dependency,
   no log-streaming config in `render.yaml` or anywhere else. Checking
   application logs means opening the `pinpoint` web service in the
   Render dashboard and reading its **Logs** tab directly; do not assume
   a `render logs`-style command exists.

3. **Compare the live commit against `main`.** Take `/health`'s `.commit`
   field from step 1 and compare it against:

   ```
   git rev-parse origin/main
   ```

   (or the equivalent `gh api` call). A mismatch tells you whether
   production is actually running the latest merged code or something
   older/different.

4. **Decide rollback vs. fix-forward**, using the same two paths
   `docs/release-process.md`'s "Rollback" section and the `release` skill
   both name:

   - **Render dashboard Redeploy (fast).** Use this when the live commit
     is bad and a known-good previous deploy exists — open the
     `pinpoint` service's **Deploys** tab and **Redeploy** the last
     successful build. Fastest path back to a working service; does not
     touch git history.
   - **`git revert <sha>` + push through CI (slower).** Use this when the
     fix is small and there is time for a full `backend` → `frontend` →
     `stack` → `deploy` run, or when keeping `main` and the deployed
     commit in sync matters more than speed.

   This skill only decides and writes down which path fits — it does not
   click Redeploy or push a revert itself. That action is for a human.

5. **Write up the incident.** Create exactly one new file at
   `ops/incidents/<YYYY-MM-DD>-<short-slug>.md` (see
   `ops/incidents/README.md` for the naming convention) containing, at
   minimum, with the level of detail `docs/ai-usage-report.md`'s entries
   already use — not a one-liner:

   - **What broke** — the symptom as observed.
   - **When/how it was detected** — what first surfaced it.
   - **What was checked** — `/health`, the Logs tab, and the live-SHA-
     vs-`main` comparison from steps 1–3, with what each one showed.
   - **The decision and why** — rollback or fix-forward, and the
     reasoning from step 4.
   - **The outcome** — what happened once the decision was carried out.
