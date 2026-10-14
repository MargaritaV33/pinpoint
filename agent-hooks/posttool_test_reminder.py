#!/usr/bin/env python3
"""PostToolUse reminder for Claude Code's Edit, Write and MultiEdit tools
(Python standard library only).

After a file under backend/ or frontend/ is edited, this prints a reminder of
the test command to run. It never runs anything and never blocks:
exit 0 always, or exit 1 (a non-blocking error Claude Code shows) when its
input is unusable. It prints nothing for any other path.

Channel: for PostToolUse, plain stdout at exit 0 is shown to the person but not
to the model. JSON on stdout with hookSpecificOutput.additionalContext is added
to the model's context, so the reminder is printed in that form. Whether it
really reaches the agent is confirmed in a live run (agent-hooks/README.md).
"""

import json
import ntpath
import os
import posixpath
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
IS_WINDOWS = os.name == "nt"
EDIT_TOOLS = ("Edit", "Write", "MultiEdit")

REMINDERS = {
    "backend": "You edited a file under backend/. Before you finish or commit, run `make test` (the backend suite).",
    "frontend": "You edited a file under frontend/. Before you finish or commit, run `make frontend-test` (the frontend unit tests).",
}


def canon(path, cwd):
    """Absolute, slash-separated, normalised path; Windows paths compare case-blind."""
    p = path.replace("\\", "/")
    if IS_WINDOWS:
        p = re.sub(r"^/([A-Za-z])(?=/|$)", r"\1:", p)
    if re.match(r"^[A-Za-z]:/", p):
        out = ntpath.normpath(p).replace("\\", "/")
    elif p.startswith("/"):
        out = posixpath.normpath(p)
        if out.startswith("//"):
            out = out[1:]
    else:
        return canon((cwd or str(REPO_ROOT)) + "/" + p, None)
    return out.lower() if IS_WINDOWS else out


def area_of(file_path, cwd):
    """Return 'backend', 'frontend' or None for a file path."""
    root = canon(str(REPO_ROOT), None)
    full = canon(file_path, cwd)
    if not full.startswith(root + "/"):
        return None
    first = full[len(root) + 1 :].split("/", 1)
    if len(first) < 2:  # a file directly in the repo root
        return None
    return first[0] if first[0] in REMINDERS else None


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace"))
        if not isinstance(data, dict):
            raise ValueError("stdin JSON is not an object")
        tool = data.get("tool_name")
        if tool not in EDIT_TOOLS:
            return 0
        tool_input = data.get("tool_input")
        file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
        if not isinstance(file_path, str) or not file_path:
            return 0
        cwd = data.get("cwd")
        area = area_of(file_path, cwd if isinstance(cwd, str) and cwd else None)
    except Exception as exc:  # non-blocking by contract: exit 1, never 2
        msg = f"{type(exc).__name__}: {exc}".replace("\n", " ")[:200]
        print(f"pinpoint test reminder: internal problem ({msg}); no reminder given.", file=sys.stderr)
        return 1
    if area:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": "Pinpoint hook reminder: " + REMINDERS[area],
                    }
                }
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
