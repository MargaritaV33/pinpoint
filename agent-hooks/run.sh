#!/bin/sh
# Single entry point for both hooks:  sh run.sh <script>.py
# Hook input arrives on stdin and is passed through to the script untouched.
#
# Picks the interpreter by trying `python3`, then `python`. A candidate is used
# only if a probe run succeeds, so the Windows Store `python3` stub (it exists
# on PATH but does not run Python) is skipped and `python` is chosen. Not
# `uv`, not `py`, no absolute path.
#
# No interpreter found is FAIL-OPEN by decision: exit 1 (a non-blocking error)
# with a message that the guardrails are NOT active. See agent-hooks/README.md.

script="$1"
if [ -z "$script" ]; then
  echo "agent-hooks/run.sh: usage: sh run.sh <script>.py (guardrails NOT active)" >&2
  exit 1
fi

# Directory of this file, in pure sh (handles / and \ separators, no dirname).
case "$0" in
  */*) dir="${0%/*}" ;;
  *\\*) dir="${0%\\*}" ;;
  *) dir="." ;;
esac

for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 &&
    "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" </dev/null >/dev/null 2>&1; then
    exec "$candidate" "$dir/$script"
  fi
done

echo "agent-hooks: no working Python 3.8+ found (tried python3, then python). The guardrails are NOT active: this command was not checked. Install Python 3.8+ and make 'python3' or 'python' run it, then restart Claude Code." >&2
exit 1
