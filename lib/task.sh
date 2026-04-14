#!/usr/bin/env bash
# GARC task.sh — Google Tasks operations
# list / show / create / update / done / delete / clear-completed / tasklists

TASKS_HELPER="${GARC_DIR}/scripts/garc-tasks-helper.py"

garc_task() {
  local subcommand="${1:-help}"
  shift || true

  case "${subcommand}" in
    list)            garc_task_list "$@" ;;
    show)            garc_task_show "$@" ;;
    create)          garc_task_create "$@" ;;
    update)          garc_task_update "$@" ;;
    done)            garc_task_done "$@" ;;
    delete)          garc_task_delete "$@" ;;
    clear-completed) garc_task_clear_completed "$@" ;;
    tasklists)       garc_task_tasklists "$@" ;;
    *)
      cat <<EOF
Usage: garc task <subcommand> [options]

Subcommands:
  list          [--list <id>] [--completed] [--format table|json]
  show          <task_id> [--list <id>]
  create        "<title>" [--due YYYY-MM-DD] [--notes <text>] [--list <id>] [--parent <id>]
  update        <task_id> [--title <text>] [--due YYYY-MM-DD] [--notes <text>] [--list <id>]
  done          <task_id> [--list <id>]
  delete        <task_id> [--list <id>]
  clear-completed  [--list <id>]
  tasklists     Show all task lists

Examples:
  garc task list
  garc task list --completed --format json
  garc task create "Write Q1 report" --due 2026-04-30 --notes "Include revenue section"
  garc task update abc123 --due 2026-05-01
  garc task done abc123
  garc task delete abc123
  garc task tasklists
EOF
      return 1
      ;;
  esac
}

garc_task_list() {
  local tasklist="@default" completed="" format="table"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --list|-l) tasklist="$2"; shift 2 ;;
      --completed) completed="--completed"; shift ;;
      --format|-f) format="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  python3 "${TASKS_HELPER}" --tasklist "${tasklist}" --format "${format}" list ${completed}
}

garc_task_show() {
  local task_id="${1:-}" tasklist="@default"
  shift || true

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --list|-l) tasklist="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  [[ -z "${task_id}" ]] && { echo "Usage: garc task show <task_id> [--list <id>]"; return 1; }

  python3 "${TASKS_HELPER}" --tasklist "${tasklist}" show --task-id "${task_id}"
}

garc_task_create() {
  local title="" tasklist="@default" due="" notes="" parent=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --list|-l) tasklist="$2"; shift 2 ;;
      --due|-d) due="$2"; shift 2 ;;
      --notes|-n) notes="$2"; shift 2 ;;
      --parent|-p) parent="$2"; shift 2 ;;
      *) title="${title:+${title} }$1"; shift ;;
    esac
  done

  [[ -z "${title}" ]] && {
    echo "Usage: garc task create \"<title>\" [--due YYYY-MM-DD] [--notes <text>] [--list <id>]"
    return 1
  }

  python3 "${TASKS_HELPER}" --tasklist "${tasklist}" create \
    --title "${title}" \
    ${due:+--due "${due}"} \
    ${notes:+--notes "${notes}"} \
    ${parent:+--parent "${parent}"}
}

garc_task_update() {
  local task_id="${1:-}" tasklist="@default" title="" due="" notes=""
  shift || true

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --list|-l) tasklist="$2"; shift 2 ;;
      --title|-t) title="$2"; shift 2 ;;
      --due|-d) due="$2"; shift 2 ;;
      --notes|-n) notes="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  [[ -z "${task_id}" ]] && {
    echo "Usage: garc task update <task_id> [--title <text>] [--due YYYY-MM-DD] [--notes <text>]"
    return 1
  }

  python3 "${TASKS_HELPER}" --tasklist "${tasklist}" update \
    --task-id "${task_id}" \
    ${title:+--title "${title}"} \
    ${due:+--due "${due}"} \
    ${notes:+--notes "${notes}"}
}

garc_task_done() {
  local task_id="${1:-}" tasklist="@default"
  shift || true

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --list|-l) tasklist="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  [[ -z "${task_id}" ]] && { echo "Usage: garc task done <task_id> [--list <id>]"; return 1; }

  python3 "${TASKS_HELPER}" --tasklist "${tasklist}" complete --task-id "${task_id}"
}

garc_task_delete() {
  local task_id="${1:-}" tasklist="@default"
  shift || true

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --list|-l) tasklist="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  [[ -z "${task_id}" ]] && { echo "Usage: garc task delete <task_id> [--list <id>]"; return 1; }

  echo "Delete task ${task_id}? [y/N]"
  read -r confirm
  [[ "${confirm}" != "y" ]] && echo "Cancelled." && return 0

  python3 "${TASKS_HELPER}" --tasklist "${tasklist}" delete --task-id "${task_id}"
}

garc_task_clear_completed() {
  local tasklist="@default"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --list|-l) tasklist="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  echo "Clear all completed tasks from '${tasklist}'? [y/N]"
  read -r confirm
  [[ "${confirm}" != "y" ]] && echo "Cancelled." && return 0

  python3 "${TASKS_HELPER}" --tasklist "${tasklist}" clear-completed
}

garc_task_tasklists() {
  python3 "${TASKS_HELPER}" list-tasklists
}
