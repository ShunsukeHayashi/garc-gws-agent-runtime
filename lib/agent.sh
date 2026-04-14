#!/usr/bin/env bash
# GARC agent.sh — Agent registry management via Google Sheets

garc_agent() {
  local subcommand="${1:-help}"
  shift || true

  case "${subcommand}" in
    list)     garc_agent_list "$@" ;;
    register) garc_agent_register "$@" ;;
    show)     garc_agent_show "$@" ;;
    *)
      echo "Usage: garc agent <list|register|show>"
      return 1
      ;;
  esac
}

# garc agent list
# Lists registered agents from Google Sheets
garc_agent_list() {
  local sheets_id="${GARC_SHEETS_ID:-}"
  if [[ -z "${sheets_id}" ]]; then
    echo "Error: GARC_SHEETS_ID not set" >&2
    return 1
  fi

  echo "Registered agents (Sheets: ${sheets_id}):"
  python3 "${GARC_DIR}/scripts/garc-sheets-helper.py" agent-list \
    --sheets-id "${sheets_id}"
}

# garc agent register [--file <yaml_file>]
# Registers agents from agents.yaml into Google Sheets
garc_agent_register() {
  local yaml_file="${GARC_DIR}/agents.yaml"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --file|-f) yaml_file="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  if [[ ! -f "${yaml_file}" ]]; then
    echo "Error: agents.yaml not found at ${yaml_file}" >&2
    return 1
  fi

  local sheets_id="${GARC_SHEETS_ID:-}"
  if [[ -z "${sheets_id}" ]]; then
    echo "Error: GARC_SHEETS_ID not set" >&2
    return 1
  fi

  echo "Registering agents from ${yaml_file}..."
  python3 "${GARC_DIR}/scripts/garc-sheets-helper.py" agent-register \
    --sheets-id "${sheets_id}" \
    --yaml-file "${yaml_file}"
}

# garc agent show <agent_id>
garc_agent_show() {
  local agent_id="${1:-}"

  if [[ -z "${agent_id}" ]]; then
    echo "Usage: garc agent show <agent_id>"
    return 1
  fi

  python3 "${GARC_DIR}/scripts/garc-sheets-helper.py" agent-show \
    --sheets-id "${GARC_SHEETS_ID:-}" \
    --agent-id "${agent_id}"
}
