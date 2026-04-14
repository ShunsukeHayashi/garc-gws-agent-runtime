#!/usr/bin/env bash
# GARC gmail.sh — Full Gmail operations
# send / search / read / inbox / draft / reply / labels / profile

GMAIL_HELPER="${GARC_DIR}/scripts/garc-gmail-helper.py"

garc_gmail() {
  local subcommand="${1:-help}"
  shift || true

  case "${subcommand}" in
    send)    garc_gmail_send "$@" ;;
    reply)   garc_gmail_reply "$@" ;;
    search)  garc_gmail_search "$@" ;;
    read)    garc_gmail_read "$@" ;;
    inbox)   garc_gmail_inbox "$@" ;;
    draft)   garc_gmail_draft "$@" ;;
    labels)  garc_gmail_labels "$@" ;;
    profile) garc_gmail_profile "$@" ;;
    *)
      cat <<EOF
Usage: garc gmail <subcommand> [options]

Subcommands:
  send     --to <email> --subject <text> --body <text> [--cc <email>] [--html]
  reply    --thread-id <id> --message-id <id> --to <email> --subject <text> --body <text>
  search   <query> [--max N] [--body]
  read     <message_id>
  inbox    [--max N] [--unread]
  draft    --to <email> --subject <text> --body <text> [--cc <email>]
  labels   (list all Gmail labels)
  profile  (show account info)

Examples:
  garc gmail send --to manager@co.com --subject "Weekly Report" --body "..."
  garc gmail search "from:boss@co.com subject:invoice" --max 10
  garc gmail inbox --unread --max 20
  garc gmail read abc123def456
EOF
      return 1
      ;;
  esac
}

garc_gmail_send() {
  local to="" subject="" body="" cc="" bcc="" html="" reply_to=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --to) to="$2"; shift 2 ;;
      --subject|-s) subject="$2"; shift 2 ;;
      --body|-b) body="$2"; shift 2 ;;
      --cc) cc="$2"; shift 2 ;;
      --bcc) bcc="$2"; shift 2 ;;
      --html) html="--html"; shift ;;
      --reply-to) reply_to="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  if [[ -z "${to}" ]] || [[ -z "${subject}" ]] || [[ -z "${body}" ]]; then
    echo "Usage: garc gmail send --to <email> --subject <text> --body <text>"
    return 1
  fi

  if [[ "${DRY_RUN:-false}" == "true" ]]; then
    echo "[dry-run] Would send email:"
    echo "  To: ${to}"
    echo "  Subject: ${subject}"
    echo "  Body: ${body:0:100}..."
    return 0
  fi

  local gate
  gate=$(python3 "${GARC_DIR}/scripts/garc-auth-helper.py" suggest "send email" 2>/dev/null | \
    grep "Gate requirement" | grep -oE "(none|preview|approval)" || echo "preview")

  if [[ "${gate}" != "none" ]]; then
    echo "⚠️  Gate: preview — Confirm send to ${to}? [y/N]"
    read -r confirm
    [[ "${confirm}" != "y" ]] && echo "Cancelled." && return 0
  fi

  python3 "${GMAIL_HELPER}" send \
    --to "${to}" \
    --subject "${subject}" \
    --body "${body}" \
    ${cc:+--cc "${cc}"} \
    ${bcc:+--bcc "${bcc}"} \
    ${html} \
    ${reply_to:+--reply-to "${reply_to}"}
}

garc_gmail_reply() {
  local thread_id="" message_id="" to="" subject="" body=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --thread-id) thread_id="$2"; shift 2 ;;
      --message-id) message_id="$2"; shift 2 ;;
      --to) to="$2"; shift 2 ;;
      --subject|-s) subject="$2"; shift 2 ;;
      --body|-b) body="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  [[ -z "${thread_id}" ]] || [[ -z "${to}" ]] || [[ -z "${body}" ]] && {
    echo "Usage: garc gmail reply --thread-id <id> --to <email> --body <text>"
    return 1
  }

  python3 "${GMAIL_HELPER}" reply \
    --thread-id "${thread_id}" \
    --message-id "${message_id:-${thread_id}}" \
    --to "${to}" \
    --subject "${subject:-Re: (no subject)}" \
    --body "${body}"
}

garc_gmail_search() {
  local query="" max=20 body_flag=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --max|-n) max="$2"; shift 2 ;;
      --body) body_flag="--body"; shift ;;
      *) query="${query:+${query} }$1"; shift ;;
    esac
  done

  [[ -z "${query}" ]] && { echo "Usage: garc gmail search <query>"; return 1; }

  python3 "${GMAIL_HELPER}" search "${query}" --max "${max}" ${body_flag}
}

garc_gmail_read() {
  [[ -z "${1:-}" ]] && { echo "Usage: garc gmail read <message_id>"; return 1; }
  python3 "${GMAIL_HELPER}" read "$1"
}

garc_gmail_inbox() {
  local max=20 unread_flag=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --max|-n) max="$2"; shift 2 ;;
      --unread) unread_flag="--unread"; shift ;;
      *) shift ;;
    esac
  done

  python3 "${GMAIL_HELPER}" inbox --max "${max}" ${unread_flag}
}

garc_gmail_draft() {
  local to="" subject="" body="" cc=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --to) to="$2"; shift 2 ;;
      --subject|-s) subject="$2"; shift 2 ;;
      --body|-b) body="$2"; shift 2 ;;
      --cc) cc="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  [[ -z "${to}" ]] || [[ -z "${subject}" ]] || [[ -z "${body}" ]] && {
    echo "Usage: garc gmail draft --to <email> --subject <text> --body <text>"
    return 1
  }

  python3 "${GMAIL_HELPER}" draft \
    --to "${to}" --subject "${subject}" --body "${body}" \
    ${cc:+--cc "${cc}"}
}

garc_gmail_labels() {
  python3 "${GMAIL_HELPER}" labels
}

garc_gmail_profile() {
  python3 "${GMAIL_HELPER}" profile
}
