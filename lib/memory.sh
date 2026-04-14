#!/usr/bin/env bash
# GARC memory.sh — Memory sync with Google Sheets
# Google Sheets replaces Lark Base as the memory backend

garc_memory() {
  local subcommand="${1:-help}"
  shift || true

  case "${subcommand}" in
    pull)   garc_memory_pull "$@" ;;
    push)   garc_memory_push "$@" ;;
    search) garc_memory_search "$@" ;;
    add)    garc_memory_add "$@" ;;
    *)
      echo "Usage: garc memory <pull|push|search|add>"
      return 1
      ;;
  esac
}

# garc memory pull
# Downloads memory entries from Google Sheets to local cache
garc_memory_pull() {
  local agent_id="${GARC_DEFAULT_AGENT:-main}"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --agent) agent_id="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  local sheets_id="${GARC_SHEETS_ID:-}"
  if [[ -z "${sheets_id}" ]]; then
    echo "Error: GARC_SHEETS_ID not set" >&2
    return 1
  fi

  echo "Pulling memory from Google Sheets (${sheets_id})..."

  local cache_dir="${GARC_CACHE_DIR}/workspace/${agent_id}"
  mkdir -p "${cache_dir}/memory"

  local output_file="${cache_dir}/memory/$(date +%Y-%m-%d).md"

  python3 "${GARC_DIR}/scripts/garc-sheets-helper.py" memory-pull \
    --sheets-id "${sheets_id}" \
    --agent-id "${agent_id}" \
    --output "${output_file}"

  echo "✅ Memory pulled to ${output_file}"
}

# garc memory push
# Uploads local memory to Google Sheets
garc_memory_push() {
  local agent_id="${GARC_DEFAULT_AGENT:-main}"
  local message=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --agent) agent_id="$2"; shift 2 ;;
      --message|-m) message="$2"; shift 2 ;;
      *) message="$1"; shift ;;
    esac
  done

  local sheets_id="${GARC_SHEETS_ID:-}"
  if [[ -z "${sheets_id}" ]]; then
    echo "Error: GARC_SHEETS_ID not set" >&2
    return 1
  fi

  if [[ -z "${message}" ]]; then
    echo "Usage: garc memory push \"<memory entry>\""
    return 1
  fi

  echo "Pushing memory to Google Sheets..."

  python3 "${GARC_DIR}/scripts/garc-sheets-helper.py" memory-push \
    --sheets-id "${sheets_id}" \
    --agent-id "${agent_id}" \
    --entry "${message}" \
    --timestamp "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

  echo "✅ Memory entry saved"
}

# garc memory search <query>
# Searches memory entries in Google Sheets
garc_memory_search() {
  local query="$*"

  if [[ -z "${query}" ]]; then
    echo "Usage: garc memory search \"<query>\""
    return 1
  fi

  local sheets_id="${GARC_SHEETS_ID:-}"
  if [[ -z "${sheets_id}" ]]; then
    echo "Error: GARC_SHEETS_ID not set" >&2
    return 1
  fi

  echo "Searching memory for: ${query}"

  python3 "${GARC_DIR}/scripts/garc-sheets-helper.py" memory-search \
    --sheets-id "${sheets_id}" \
    --query "${query}"
}

# garc memory add "<entry>"
# Quick alias for pushing a single memory entry
garc_memory_add() {
  garc_memory_push "$@"
}
