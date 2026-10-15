# Incidents

This directory holds one write-up per production incident. A file only
appears here once something real has actually happened in production. Entries
are blameless: they name roles and systems (the deploy job, the Blueprint, the
agent, the owner), never people, and every fact in a timeline has a source or
is marked unknown. For what to do while an incident is happening, start at
[`../runbook.md`](../runbook.md).

## Entries

| Date | Entry | What it was |
|---|---|---|
| 2026-10-14 | [Render deploy exit 127](2026-10-14-render-deploy-exit-127.md) | First Render deploy crashed at start: a `dockerCommand` override in `render.yaml` was run as one not-found executable. Our configuration; fixed by removing the override. |
| 2026-10-14 | [Render platform outage](2026-10-14-render-platform-outage.md) | The CI `deploy` job failed at the hook with HTTP 500 on three pushes while status.render.com listed an incident on builds and deploys. The provider's incident; our process gap was labelling the first failure transient without checking it. |

## Naming convention

`ops/incidents/<YYYY-MM-DD>-<short-slug>.md`, e.g.
`2026-11-03-health-check-500.md`. The date is when the incident was
detected (not necessarily when it started), and the slug is a few
hyphenated words naming the symptom.

## What goes in an entry

Each entry is written by following the `incident-response` skill
(`.agents/skills/incident-response/SKILL.md`), which fixes the shape:
what broke, when/how it was detected, what was checked (`/health`, the
Render dashboard Logs tab, and the live commit compared against `main`),
the rollback-vs-fix-forward decision and why, and the outcome. Write at
the level of detail `docs/ai-usage-report.md`'s entries already use —
one incident is one real record, not a one-liner.
