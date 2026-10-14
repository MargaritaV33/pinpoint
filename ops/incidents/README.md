# Incidents

This directory holds one write-up per production incident. It starts
empty — there is no incident history yet, and a file only appears here
once something real has actually happened in production.

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
