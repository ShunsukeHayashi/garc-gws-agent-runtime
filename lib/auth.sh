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
    suggest)         garc_auth_suggest "$@" ;;
    check)           garc_auth_check "$@" ;;
    login)           garc_auth_login "$@" ;;
    status)          garc_auth_status "$@" ;;
    revoke)          garc_auth_revoke "$@" ;;
    service-account) garc_auth_service_account "$@" ;;
    *)
      cat <<EOF
Usage: garc auth <subcommand>

Subcommands:
  suggest "<task>"          Infer minimum OAuth scopes for a task
  check [--profile <p>]    Check if current token covers required scopes
  login [--profile <p>]    Launch OAuth2 authorization flow
  status                   Show current token info and scopes
  revoke                   Revoke and delete the stored OAuth token
  service-account verify   Verify service account credentials and scopes
EOF
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

# garc auth login [--profile <profile>] [--type oauth|service-account]
# Launches OAuth2 authorization flow, or validates service account
garc_auth_login() {
  local profile="writer"
  local auth_type="oauth"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) profile="$2"; shift 2 ;;
      --type)    auth_type="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  if [[ "${auth_type}" == "service-account" ]]; then
    garc_auth_service_account verify
    return $?
  fi

  python3 "${AUTH_HELPER}" login --profile "${profile}"
}

# garc auth status
# Shows current token scopes
garc_auth_status() {
  python3 "${AUTH_HELPER}" status
}

# garc auth revoke
# Revoke and delete the stored OAuth token
garc_auth_revoke() {
  python3 "${AUTH_HELPER}" revoke
}

# garc auth service-account <verify|info>
garc_auth_service_account() {
  local sub="${1:-verify}"
  shift || true

  local sa_file="${GARC_SERVICE_ACCOUNT_FILE:-${HOME}/.garc/service_account.json}"

  case "${sub}" in
    verify)
      if [[ ! -f "${sa_file}" ]]; then
        echo "❌ Service account file not found: ${sa_file}"
        echo "   Set GARC_SERVICE_ACCOUNT_FILE in ~/.garc/config.env"
        echo "   Or download from Google Cloud Console → IAM & Admin → Service Accounts"
        return 1
      fi
      echo "Verifying service account credentials..."
      python3 "${AUTH_HELPER}" service-account-verify --file "${sa_file}"
      ;;
    info)
      if [[ ! -f "${sa_file}" ]]; then
        echo "❌ Service account file not found: ${sa_file}"
        return 1
      fi
      python3 -c "
import json
with open('${sa_file}') as f:
    sa = json.load(f)
print('Service Account:')
print(f\"  Email : {sa.get('client_email', 'N/A')}\")
print(f\"  Project: {sa.get('project_id', 'N/A')}\")
print(f\"  Type   : {sa.get('type', 'N/A')}\")
"
      ;;
    *)
      echo "Usage: garc auth service-account <verify|info>"
      return 1
      ;;
  esac
}
