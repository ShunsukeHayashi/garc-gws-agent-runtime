#!/usr/bin/env bash
# GARC heartbeat.sh — System state logging to Google Sheets

garc_heartbeat() {
  local agent_id="${GARC_DEFAULT_AGENT:-main}"
  local status="ok"
  local notes=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --agent) agent_id="$2"; shift 2 ;;
      --status) status="$2"; shift 2 ;;
      --notes) notes="$2"; shift 2 ;;
      *) notes="$1"; shift ;;
    esac
  done

  local sheets_id="${GARC_SHEETS_ID:-}"
  if [[ -z "${sheets_id}" ]]; then
    echo "Error: GARC_SHEETS_ID not set" >&2
    return 1
  fi

  local timestamp
  timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  echo "Recording heartbeat to Sheets..."

  python3 "${GARC_DIR}/scripts/garc-sheets-helper.py" heartbeat \
    --sheets-id "${sheets_id}" \
    --agent-id "${agent_id}" \
    --status "${status}" \
    --notes "${notes}" \
    --timestamp "${timestamp}"

  # Also update local HEARTBEAT.md
  local workspace_dir="${GARC_CACHE_DIR}/workspace/${agent_id}"
  if [[ -d "${workspace_dir}" ]]; then
    cat > "${workspace_dir}/HEARTBEAT.md" <<EOF
# HEARTBEAT — System State

agent_id: ${agent_id}
last_heartbeat: ${timestamp}
status: ${status}
notes: ${notes}
platform: Google Workspace
sheets_id: ${sheets_id}
EOF
  fi

  echo "✅ Heartbeat logged: ${timestamp} [${status}]"
}
