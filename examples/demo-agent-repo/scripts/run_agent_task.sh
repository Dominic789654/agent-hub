#!/usr/bin/env bash
set -euo pipefail

agent_name="${1:-agent}"
task_id="${2:-unknown-task}"
payload="${3:-}"

echo "[agent-wrapper] agent=${agent_name} task_id=${task_id}"
echo "[agent-wrapper] repo=$(pwd)"
echo "[agent-wrapper] payload=${payload}"

case "${payload}" in
  *"manual review"*|*"needs human"*|*"ambiguous"*)
    echo "[agent-wrapper] detected ambiguous request; manual review suggested"
    ;;
  *"fail"*|*"broken"*)
    echo "[agent-wrapper] simulated failure for demo" >&2
    exit 1
    ;;
  *)
    echo "[agent-wrapper] simulated assistant run completed"
    ;;
esac
