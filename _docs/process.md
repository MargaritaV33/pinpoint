# Process

- Tasks are GitHub issues, one at a time. The issue tracker is the only
  backlog.
- Read the acceptance criteria before starting and before closing.
- Start a fresh session for each step. The session that implemented something
  never judges it.
- Commit regularly.

## Roles

- PM — grooms a task before anyone implements it, follows `_docs/team/pm.md`
- Engineer — implements one groomed task, follows
  `_docs/team/software-engineer.md`
- QA — checks the result against the acceptance criteria, follows
  `_docs/team/qa-engineer.md`

## Orchestrator

The main session is the orchestrator. It launches the PM, the engineer and QA
as subagents. It does not groom, implement or test itself.

### Lifecycle

1. Pick the next open issue from the backlog
2. PM grooms it
3. Engineer implements it
4. QA verifies it
5. On FAIL, back to step 3 with the QA comment as input
6. On PASS, close the issue
7. Repeat until the backlog is empty

### Rules

- Do not skip step 2
- The engineer does not close the issue
- QA does not fix the code, only outputs PASS or FAIL
- The orchestrator closes the issue only after QA outputs PASS

## AI usage log

Every step appends one entry to `docs/ai-usage-report.md`: the prompt or task,
what the agent produced, what was reviewed or rejected, and how it was verified.
