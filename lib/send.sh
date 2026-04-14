#!/usr/bin/env bash
# GARC send.sh — Gmail / Google Chat message sending
# Replaces Lark IM with Gmail or Google Chat

garc_send() {
  local message=""
  local to="${GARC_GMAIL_DEFAULT_TO:-}"
  local subject="GARC Agent Notification"
  local use_chat=false
  local space_id="${GARC_CHAT_SPACE_ID:-}"

  # Parse message (first non-flag argument)
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
    echo "Usage: garc send \"<message>\" [--to <email>] [--chat] [--space <space_id>]"
    return 1
  fi

  if [[ "${use_chat}" == "true" ]]; then
    _garc_send_chat "${message}" "${space_id}"
  else
    _garc_send_gmail "${message}" "${to}" "${subject}"
  fi
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
  local space_id="$2"

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
    --message "${message}"
}
