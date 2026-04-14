#!/usr/bin/env bash
# GARC auth.sh — OAuth scope inference and authorization
# Mirrors LARC's auth.sh but for Google Workspace OAuth scopes

GARC_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GARC_DIR="$(cd "${GARC_SCRIPT_DIR}/.." && pwd)"
SCOPE_MAP="${GARC_DIR}/config/scope-map.json"
AUTH_HELPER="${GARC_DIR}/scripts/garc-auth-helper.py"

garc_auth() {
  local subcommand="${1:-help}"
  shift || true

  case "${subcommand}" in
    suggest) garc_auth_suggest "$@" ;;
    check)   garc_auth_check "$@" ;;
    login)   garc_auth_login "$@" ;;
    status)  garc_auth_status "$@" ;;
    *)
      echo "Usage: garc auth <suggest|check|login|status>"
      return 1
      ;;
  esac
}

# garc auth suggest "<task description>"
# Infers the minimum OAuth scopes required for the task
garc_auth_suggest() {
  local task_description="$*"

  if [[ -z "${task_description}" ]]; then
    echo "Usage: garc auth suggest \"<task description>\""
    echo "Example: garc auth suggest \"send expense report to manager\""
    return 1
  fi

  if ! command -v python3 &>/dev/null; then
    echo "Error: python3 is required for scope inference" >&2
    return 1
  fi

  python3 "${AUTH_HELPER}" suggest "${task_description}"
}

# garc auth check [--profile <profile>]
# Checks if current token has required scopes
garc_auth_check() {
  local profile="backoffice_agent"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) profile="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  python3 "${AUTH_HELPER}" check --profile "${profile}"
}

# garc auth login [--profile <profile>]
# Launches OAuth2 authorization flow
garc_auth_login() {
  local profile="writer"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) profile="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  python3 "${AUTH_HELPER}" login --profile "${profile}"
}

# garc auth status
# Shows current token scopes
garc_auth_status() {
  python3 "${AUTH_HELPER}" status
}
