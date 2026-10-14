---
name: implement-issue
description: Runs a Pinpoint GitHub issue through this project's full PM-grooms, Engineer-implements, QA-verifies lifecycle, including the per-issue AI usage log entry. Use this whenever the user wants to take a backlog issue from open to PASS, or asks how an issue should move through grooming/implementation/QA.
---

This project's lifecycle for taking one GitHub issue from open to done is
already fixed in `_docs/process.md` — this skill just names it step by
step so it is not reinvented each time. Only the orchestrator (the main
session, not a subagent) runs these steps; it launches PM, Engineer, and
QA as separate subagents and never grooms, implements, or tests itself.

1. **Pick the issue.** Take the next open issue from the GitHub issue
   tracker — the only backlog this project uses.

2. **PM grooms it**, following `_docs/team/pm.md`. The PM rewrites the
   issue using `_docs/task-template.md`'s four sections (Goal, Acceptance
   criteria, Out of scope, Constraints), makes every acceptance criterion
   checkable by looking at the result, and respects `_docs/decisions.md`
   rather than reopening settled questions. This step is never skipped.

3. **Engineer implements it**, following
   `_docs/team/software-engineer.md`. The engineer implements against the
   groomed acceptance criteria without changing them, stays inside the
   issue's named files/constraints, writes tests for the new behavior,
   runs the real test commands — `make test` (backend), `make
   frontend-test` (frontend), and `make integration` when the issue
   touches the API or database — and commits regularly. The engineer does
   not close the issue.

4. **QA verifies it**, following `_docs/team/qa-engineer.md`. QA re-runs
   the same real commands (`make test`, `make frontend-test`, `make
   integration` when relevant), checks each acceptance criterion against
   the running code (not against what the implementation claims to do),
   and posts one comment on the issue in QA's exact template: a verdict
   line (`## QA: PASS` or `## QA: FAIL`), one checklist line per
   acceptance criterion, and the test commands with their results. QA
   never fixes code — only reports PASS or FAIL.

5. **On FAIL**, the orchestrator sends QA's comment back to the Engineer
   as input and repeats step 3 onward. QA's comment is the only input the
   next engineering pass needs — it already says what was checked and
   what happened.

6. **On PASS**, the orchestrator — never the Engineer, never QA — closes
   the issue. This is the one closing rule this skill exists to enforce:
   neither of the other two roles has authority to close.

7. **Log every step.** Every one of steps 2–4 (PM, Engineer, QA) appends
   exactly one entry to `docs/ai-usage-report.md`'s
   `## Appendix: per-issue log`, in the same shape every existing entry
   there already uses. Match the literal structure of an existing entry —
   issue #17's entry in that file (`## 2026-10-14 — Issue #17: Align
   Python version between .python-version and the Dockerfile`) is the
   template: a dated `##` heading naming the issue number and title,
   followed by `- **PM input/output:**`, `- **Engineer input/output:**`,
   `- **Review:**`, and `- **Verification:**` bullets, each describing
   what was actually done, reviewed/rejected, and verified — not a
   one-line summary. Read that entry before writing a new one if the
   shape is unclear.

This skill does not invent any command or mechanism beyond what
`_docs/process.md`, `_docs/team/*.md`, and the `Makefile` already define.
