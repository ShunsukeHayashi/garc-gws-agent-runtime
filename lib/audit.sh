#!/usr/bin/env bash
# GARC audit.sh — Audit log viewer
# Events are appended to the 'audit' tab in Google Sheets by bin/garc.

garc_audit() {
  local subcommand="${1:-list}"
  shift || true

  case "${subcommand}" in
    list)  _audit_list "$@" ;;
    *)
      cat <<EOF
Usage: garc audit <subcommand>

Subcommands:
  list   [--agent <id>] [--since YYYY-MM-DD] [--format table|json]
         Show audit log from Google Sheets
EOF
      return 1
      ;;
  esac
}

_audit_list() {
  local sheets_id="${GARC_SHEETS_ID:-}"
  local agent_id="" since="" fmt="table"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --agent|-a) agent_id="$2"; shift 2 ;;
      --since|-s) since="$2"; shift 2 ;;
      --format|-f) fmt="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  if [[ -z "${sheets_id}" ]]; then
    echo "Error: GARC_SHEETS_ID not set" >&2
    return 1
  fi

  python3 "${GARC_DIR}/scripts/garc-sheets-helper.py" audit-list \
    --sheets-id "${sheets_id}" \
    ${agent_id:+--agent-id "${agent_id}"} \
    ${since:+--since "${since}"} \
    --format "${fmt}"
}
