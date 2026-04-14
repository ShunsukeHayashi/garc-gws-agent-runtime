#!/usr/bin/env bash
# GARC sheets.sh — Direct Google Sheets operations
# read / write / append / search / info / clear

SHEETS_HELPER="${GARC_DIR}/scripts/garc-sheets-helper.py"

garc_sheets() {
  local subcommand="${1:-help}"
  shift || true

  case "${subcommand}" in
    read)   garc_sheets_read "$@" ;;
    write)  garc_sheets_write "$@" ;;
    append) garc_sheets_append "$@" ;;
    search) garc_sheets_search "$@" ;;
    info)   garc_sheets_info "$@" ;;
    clear)  garc_sheets_clear "$@" ;;
    *)
      cat <<EOF
Usage: garc sheets <subcommand> [options]

Subcommands:
  read    --sheets-id <id> --range <A1:Z10> [--format table|json]
  write   --sheets-id <id> --range <A1> --values '[[...]]'
  append  --sheets-id <id> --sheet <name> --values '[...]'
  search  --sheets-id <id> --sheet <name> --query <text> [--column N] [--format table|json]
  info    --sheets-id <id>
  clear   --sheets-id <id> --range <A2:Z>

Defaults to GARC_SHEETS_ID if --sheets-id is omitted.

Examples:
  garc sheets info
  garc sheets read --range "memory!A:E" --format json
  garc sheets search --sheet memory --query "expense"
  garc sheets append --sheet queue --values '["main","msg","pending","preview"]'
  garc sheets write --range "agents!A2" --values '[["main","claude-sonnet-4-6"]]'
EOF
      return 1
      ;;
  esac
}

_sheets_id() {
  echo "${GARC_SHEETS_ID:-}"
}

garc_sheets_read() {
  local sheets_id="" range_="" format="table"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --sheets-id) sheets_id="$2"; shift 2 ;;
      --range|-r) range_="$2"; shift 2 ;;
      --format|-f) format="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  sheets_id="${sheets_id:-$(_sheets_id)}"
  [[ -z "${sheets_id}" ]] && { echo "Error: GARC_SHEETS_ID not set"; return 1; }
  [[ -z "${range_}" ]] && { echo "Usage: garc sheets read --range <range>"; return 1; }

  python3 "${SHEETS_HELPER}" read \
    --sheets-id "${sheets_id}" \
    --range "${range_}" \
    --format "${format}"
}

garc_sheets_write() {
  local sheets_id="" range_="" values=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --sheets-id) sheets_id="$2"; shift 2 ;;
      --range|-r) range_="$2"; shift 2 ;;
      --values|-v) values="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  sheets_id="${sheets_id:-$(_sheets_id)}"
  [[ -z "${sheets_id}" ]] && { echo "Error: GARC_SHEETS_ID not set"; return 1; }
  [[ -z "${range_}" ]] || [[ -z "${values}" ]] && {
    echo "Usage: garc sheets write --range <range> --values '[[\"value1\", \"value2\"]]'"
    return 1
  }

  python3 "${SHEETS_HELPER}" write \
    --sheets-id "${sheets_id}" \
    --range "${range_}" \
    --values "${values}"
}

garc_sheets_append() {
  local sheets_id="" sheet="" values=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --sheets-id) sheets_id="$2"; shift 2 ;;
      --sheet|-s) sheet="$2"; shift 2 ;;
      --values|-v) values="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  sheets_id="${sheets_id:-$(_sheets_id)}"
  [[ -z "${sheets_id}" ]] && { echo "Error: GARC_SHEETS_ID not set"; return 1; }
  [[ -z "${sheet}" ]] || [[ -z "${values}" ]] && {
    echo "Usage: garc sheets append --sheet <name> --values '[\"val1\", \"val2\"]'"
    return 1
  }

  python3 "${SHEETS_HELPER}" append \
    --sheets-id "${sheets_id}" \
    --sheet "${sheet}" \
    --values "${values}"
}

garc_sheets_search() {
  local sheets_id="" sheet="" query="" column=-1 format="table"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --sheets-id) sheets_id="$2"; shift 2 ;;
      --sheet|-s) sheet="$2"; shift 2 ;;
      --query|-q) query="$2"; shift 2 ;;
      --column|-c) column="$2"; shift 2 ;;
      --format|-f) format="$2"; shift 2 ;;
      *) query="${query:+${query} }$1"; shift ;;
    esac
  done

  sheets_id="${sheets_id:-$(_sheets_id)}"
  [[ -z "${sheets_id}" ]] && { echo "Error: GARC_SHEETS_ID not set"; return 1; }
  [[ -z "${sheet}" ]] || [[ -z "${query}" ]] && {
    echo "Usage: garc sheets search --sheet <name> --query <text>"
    return 1
  }

  python3 "${SHEETS_HELPER}" search \
    --sheets-id "${sheets_id}" \
    --sheet "${sheet}" \
    --query "${query}" \
    --column "${column}" \
    --format "${format}"
}

garc_sheets_info() {
  local sheets_id="${1:-}"

  [[ $# -gt 0 ]] && shift
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --sheets-id) sheets_id="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  sheets_id="${sheets_id:-$(_sheets_id)}"
  [[ -z "${sheets_id}" ]] && { echo "Error: GARC_SHEETS_ID not set"; return 1; }

  python3 "${SHEETS_HELPER}" info --sheets-id "${sheets_id}"
}

garc_sheets_clear() {
  local sheets_id="" range_=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --sheets-id) sheets_id="$2"; shift 2 ;;
      --range|-r) range_="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  sheets_id="${sheets_id:-$(_sheets_id)}"
  [[ -z "${sheets_id}" ]] && { echo "Error: GARC_SHEETS_ID not set"; return 1; }
  [[ -z "${range_}" ]] && { echo "Usage: garc sheets clear --range <range>"; return 1; }

  echo "⚠️  Clear range ${range_}? [y/N]"
  read -r confirm
  [[ "${confirm}" != "y" ]] && echo "Cancelled." && return 0

  python3 "${SHEETS_HELPER}" clear --sheets-id "${sheets_id}" --range "${range_}"
}
