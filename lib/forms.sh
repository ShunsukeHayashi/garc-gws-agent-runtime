#!/usr/bin/env bash
# GARC forms.sh — Google Forms response pipeline
# Polls Forms for new responses and auto-enqueues them via garc ingress.

FORMS_HELPER="${GARC_DIR}/scripts/garc-forms-helper.py"

garc_forms() {
  local subcommand="${1:-help}"
  shift || true

  case "${subcommand}" in
    list)           garc_forms_list "$@" ;;
    responses)      garc_forms_responses "$@" ;;
    watch)          garc_forms_watch "$@" ;;
    *)
      cat <<EOF
Usage: garc forms <subcommand>

Subcommands:
  list                           List accessible Google Forms
  responses <form_id> [--max N]  List responses for a form
  watch <form_id> --agent <id>   Poll form and auto-enqueue new responses
    [--interval <sec>]           Poll interval (default: 60)
    [--max <N>]                  Max responses per cycle (default: 10)

Examples:
  garc forms list
  garc forms responses 1xxxxxxxxxxxxxxxx
  garc forms watch 1xxxxxxxxxxxxxxxx --agent main --interval 30
EOF
      return 1
      ;;
  esac
}

garc_forms_list() {
  python3 "${FORMS_HELPER}" list-forms
}

garc_forms_responses() {
  local form_id="${1:-}"
  shift || true
  local max=50 since="" fmt="table"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --max|-n) max="$2"; shift 2 ;;
      --since) since="$2"; shift 2 ;;
      --format) fmt="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  [[ -z "${form_id}" ]] && { echo "Usage: garc forms responses <form_id> [--max N]"; return 1; }

  python3 "${FORMS_HELPER}" list-responses "${form_id}" \
    --max "${max}" \
    ${since:+--since "${since}"} \
    --format "${fmt}"
}

garc_forms_watch() {
  local form_id="${1:-}"
  shift || true
  local agent="${GARC_DEFAULT_AGENT:-main}" interval=60 max=10

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --agent|-a) agent="$2"; shift 2 ;;
      --interval|-i) interval="$2"; shift 2 ;;
      --max|-n) max="$2"; shift 2 ;;
      *) form_id="${form_id:-$1}"; shift ;;
    esac
  done

  [[ -z "${form_id}" ]] && {
    echo "Usage: garc forms watch <form_id> --agent <id> [--interval <sec>]"
    return 1
  }

  echo "👁  Watching form: ${form_id}"
  echo "   Agent: ${agent}  Interval: ${interval}s"
  echo "   Press Ctrl+C to stop."
  echo ""

  python3 "${FORMS_HELPER}" watch "${form_id}" \
    --agent "${agent}" \
    --interval "${interval}" \
    --max "${max}"
}
