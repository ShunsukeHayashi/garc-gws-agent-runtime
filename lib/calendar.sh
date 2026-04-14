#!/usr/bin/env bash
# GARC calendar.sh — Full Google Calendar operations
# list / create / update / delete / get / freebusy / quick-add / calendars

CAL_HELPER="${GARC_DIR}/scripts/garc-calendar-helper.py"

garc_calendar() {
  local subcommand="${1:-help}"
  shift || true

  case "${subcommand}" in
    list)       garc_calendar_list "$@" ;;
    create)     garc_calendar_create "$@" ;;
    update)     garc_calendar_update "$@" ;;
    delete)     garc_calendar_delete "$@" ;;
    get)        garc_calendar_get "$@" ;;
    freebusy)   garc_calendar_freebusy "$@" ;;
    quick-add)  garc_calendar_quick_add "$@" ;;
    calendars)  garc_calendar_list_cals "$@" ;;
    today)      garc_calendar_today "$@" ;;
    week)       garc_calendar_week "$@" ;;
    *)
      cat <<EOF
Usage: garc calendar <subcommand> [options]

Subcommands:
  list        [--days N] [--back N] [--calendar <id>] [--query <text>]
  today       (events for today)
  week        (events for this week)
  create      --summary <text> --start <datetime> --end <datetime> [--description <text>]
              [--location <text>] [--attendees email1 email2] [--all-day] [--recurrence <RRULE>]
  update      <event_id> [--summary <text>] [--start <dt>] [--end <dt>] [--add-attendees email...]
  delete      <event_id>
  get         <event_id>
  freebusy    --start <date> --end <date> --emails email1 [email2 ...]
  quick-add   "<natural language text>"
  calendars   (list all calendars)

Examples:
  garc calendar today
  garc calendar list --days 14
  garc calendar create --summary "Team Standup" --start "2026-04-16T10:00:00" --end "2026-04-16T10:30:00" --attendees alice@co.com bob@co.com
  garc calendar freebusy --start 2026-04-16 --end 2026-04-17 --emails alice@co.com bob@co.com
  garc calendar quick-add "Lunch with Alice tomorrow at noon"
EOF
      return 1
      ;;
  esac
}

garc_calendar_list() {
  local days=7 back=0 calendar="primary" query=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --days|-n) days="$2"; shift 2 ;;
      --back) back="$2"; shift 2 ;;
      --calendar|-c) calendar="$2"; shift 2 ;;
      --query|-q) query="$2"; shift 2 ;;
      --max) shift 2 ;;  # ignored, use default
      *) shift ;;
    esac
  done

  python3 "${CAL_HELPER}" list \
    --calendar "${calendar}" \
    --days "${days}" \
    --back "${back}" \
    ${query:+--query "${query}"}
}

garc_calendar_today() {
  python3 "${CAL_HELPER}" list --calendar primary --days 1 --back 0
}

garc_calendar_week() {
  local back=0
  # Calculate days until end of week
  local day_of_week
  day_of_week=$(date +%u)  # 1=Mon, 7=Sun
  local days_left=$(( 7 - day_of_week + 1 ))
  python3 "${CAL_HELPER}" list --calendar primary --days "${days_left}" --back "${day_of_week}"
}

garc_calendar_create() {
  local summary="" start="" end="" description="" location="" timezone="Asia/Tokyo"
  local all_day="" recurrence="" no_notify="" calendar="primary"
  local attendees=()

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --summary|-s) summary="$2"; shift 2 ;;
      --start) start="$2"; shift 2 ;;
      --end) end="$2"; shift 2 ;;
      --description|-d) description="$2"; shift 2 ;;
      --location|-l) location="$2"; shift 2 ;;
      --attendees) shift
        while [[ $# -gt 0 ]] && [[ "$1" != --* ]]; do
          attendees+=("$1"); shift
        done ;;
      --all-day) all_day="--all-day"; shift ;;
      --recurrence) recurrence="$2"; shift 2 ;;
      --no-notify) no_notify="--no-notify"; shift ;;
      --calendar|-c) calendar="$2"; shift 2 ;;
      --timezone|-tz) timezone="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  [[ -z "${summary}" ]] || [[ -z "${start}" ]] || [[ -z "${end}" ]] && {
    echo "Usage: garc calendar create --summary <text> --start <datetime> --end <datetime>"
    return 1
  }

  # Gate check for calendar write
  if [[ "${DRY_RUN:-false}" == "true" ]]; then
    echo "[dry-run] Would create event: ${summary} (${start} → ${end})"
    return 0
  fi

  python3 "${CAL_HELPER}" create \
    --summary "${summary}" \
    --start "${start}" \
    --end "${end}" \
    --calendar "${calendar}" \
    --timezone "${timezone}" \
    ${description:+--description "${description}"} \
    ${location:+--location "${location}"} \
    ${all_day} \
    ${no_notify} \
    ${recurrence:+--recurrence "${recurrence}"} \
    ${attendees[@]:+--attendees "${attendees[@]}"}
}

garc_calendar_update() {
  local event_id="${1:-}"
  shift || true

  [[ -z "${event_id}" ]] && { echo "Usage: garc calendar update <event_id> [--summary ...] [--start ...] [--end ...]"; return 1; }

  python3 "${CAL_HELPER}" update "${event_id}" "$@"
}

garc_calendar_delete() {
  local event_id="${1:-}"
  local calendar="primary"

  [[ -z "${event_id}" ]] && { echo "Usage: garc calendar delete <event_id>"; return 1; }

  echo "⚠️  Delete event ${event_id}? [y/N]"
  read -r confirm
  [[ "${confirm}" != "y" ]] && echo "Cancelled." && return 0

  python3 "${CAL_HELPER}" delete "${event_id}" --calendar "${calendar}"
}

garc_calendar_get() {
  [[ -z "${1:-}" ]] && { echo "Usage: garc calendar get <event_id>"; return 1; }
  python3 "${CAL_HELPER}" get "$1"
}

garc_calendar_freebusy() {
  local start="" end="" timezone="Asia/Tokyo"
  local emails=()

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --start) start="$2"; shift 2 ;;
      --end) end="$2"; shift 2 ;;
      --timezone|-tz) timezone="$2"; shift 2 ;;
      --emails) shift
        while [[ $# -gt 0 ]] && [[ "$1" != --* ]]; do
          emails+=("$1"); shift
        done ;;
      *) shift ;;
    esac
  done

  [[ -z "${start}" ]] || [[ ${#emails[@]} -eq 0 ]] && {
    echo "Usage: garc calendar freebusy --start <date> --end <date> --emails email1 [email2 ...]"
    return 1
  }

  [[ -z "${end}" ]] && end="${start}"

  python3 "${CAL_HELPER}" freebusy \
    --start "${start}" \
    --end "${end}" \
    --timezone "${timezone}" \
    --emails "${emails[@]}"
}

garc_calendar_quick_add() {
  local text="$*"
  [[ -z "${text}" ]] && { echo "Usage: garc calendar quick-add \"<text>\""; return 1; }
  python3 "${CAL_HELPER}" quick-add "${text}"
}

garc_calendar_list_cals() {
  python3 "${CAL_HELPER}" calendars
}
