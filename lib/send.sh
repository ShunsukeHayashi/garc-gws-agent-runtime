#!/usr/bin/env bash
# GARC send.sh — Gmail / Google Chat message sending
# Replaces Lark IM with Gmail or Google Chat

garc_send() {
  local subcommand="${1:-}"

  # Support 'garc send chat ...' / 'garc send email ...' sub-dispatching
  case "${subcommand}" in
    chat)
      shift
      _garc_send_chat_cmd "$@"
      return $?
      ;;
    email)
      shift
      ;;  # fall through to default Gmail path
  esac

  local message=""
  local to="${GARC_GMAIL_DEFAULT_TO:-}"
  local subject="GARC Agent Notification"
  local use_chat=false
  local space_id="${GARC_CHAT_SPACE_ID:-}"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --to) to="$2"; shift 2 ;;
      --subject|-s) subject="$2"; shift 2 ;;
      --chat) use_chat=true; shift ;;
      --space) space_id="$2"; shift 2 ;;
      *) message="$1"; shift ;;
    esac
  done

  if [[ -z "${message}" ]]; then
    cat <<EOF
Usage:
  garc send "<message>" [--to <email>] [--subject <s>]   # Gmail
  garc send --chat "<message>" [--space <space_id>]       # Chat
  garc send chat <subcommand>                             # Chat management
    chat send "<message>" [--space <id>] [--thread <key>]
    chat list-spaces
    chat list-messages [--space <id>] [--max N]
EOF
    return 1
  fi

  if [[ "${use_chat}" == "true" ]]; then
    _garc_send_chat "${message}" "${space_id}"
  else
    _garc_send_gmail "${message}" "${to}" "${subject}"
  fi
}

_garc_send_chat_cmd() {
  local sub="${1:-send}"
  shift || true
  local message="" space_id="${GARC_CHAT_SPACE_ID:-}" thread_key="" max=25

  case "${sub}" in
    list-spaces)
      python3 "${GARC_DIR}/scripts/garc-chat-helper.py" list-spaces
      return $?
      ;;
    list-messages)
      while [[ $# -gt 0 ]]; do
        case "$1" in
          --space) space_id="$2"; shift 2 ;;
          --max) max="$2"; shift 2 ;;
          *) shift ;;
        esac
      done
      [[ -z "${space_id}" ]] && { echo "Error: --space required"; return 1; }
      python3 "${GARC_DIR}/scripts/garc-chat-helper.py" list-messages \
        --space-id "${space_id}" --max "${max}"
      return $?
      ;;
    send|*)
      while [[ $# -gt 0 ]]; do
        case "$1" in
          --space) space_id="$2"; shift 2 ;;
          --thread) thread_key="$2"; shift 2 ;;
          *) message="${message:+${message} }$1"; shift ;;
        esac
      done
      [[ -z "${message}" ]] && { echo "Usage: garc send chat send \"<message>\" [--space <id>]"; return 1; }
      _garc_send_chat "${message}" "${space_id}" "${thread_key}"
      return $?
      ;;
  esac
}

_garc_send_gmail() {
  local message="$1"
  local to="$2"
  local subject="$3"

  if [[ -z "${to}" ]]; then
    echo "Error: No recipient. Set GARC_GMAIL_DEFAULT_TO or use --to <email>" >&2
    return 1
  fi

  echo "Sending Gmail to ${to}..."
  echo "Subject: ${subject}"
  echo "Message: ${message}"

  if [[ "${DRY_RUN:-false}" == "true" ]]; then
    echo "[dry-run] Would send Gmail to ${to}"
    return 0
  fi

  python3 "${GARC_DIR}/scripts/garc-gmail-helper.py" send \
    --to "${to}" \
    --subject "${subject}" \
    --body "${message}"
}

_garc_send_chat() {
  local message="$1"
  local space_id="${2:-${GARC_CHAT_SPACE_ID:-}}"
  local thread_key="${3:-}"

  if [[ -z "${space_id}" ]]; then
    echo "Error: No Chat space. Set GARC_CHAT_SPACE_ID or use --space <space_id>" >&2
    return 1
  fi

  echo "Sending Google Chat message to space ${space_id}..."

  if [[ "${DRY_RUN:-false}" == "true" ]]; then
    echo "[dry-run] Would send Chat message to ${space_id}"
    return 0
  fi

  python3 "${GARC_DIR}/scripts/garc-chat-helper.py" send \
    --space-id "${space_id}" \
    --message "${message}" \
    ${thread_key:+--thread-key "${thread_key}"}
}
