#!/usr/bin/env bash
# Fails loudly if .claude/{agents,skills} has drifted from the canonical
# .agents/{agents,skills} trees. Run as: bash scripts/check-agents-sync.sh
#
# Fix a reported drift with `make sync-agents`, then re-run this script.
set -u

status=0

check_pair() {
  local canonical="$1"
  local working="$2"

  if [ ! -d "$canonical" ]; then
    echo "missing canonical directory: $canonical"
    status=1
    return
  fi

  if [ ! -d "$working" ]; then
    echo "missing working-copy directory: $working"
    status=1
    return
  fi

  if ! diff -rq "$canonical" "$working"; then
    status=1
  fi
}

check_pair ".agents/agents" ".claude/agents"
check_pair ".agents/skills" ".claude/skills"

if [ "$status" -eq 0 ]; then
  echo "agents/skills trees are in sync."
fi

exit "$status"
