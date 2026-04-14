#!/usr/bin/env bash
# GARC people.sh — Google People API: contacts and directory search

PEOPLE_HELPER="${GARC_DIR}/scripts/garc-people-helper.py"

garc_people() {
  local subcommand="${1:-help}"
  shift || true

  case "${subcommand}" in
    search)    garc_people_search "$@" ;;
    directory) garc_people_directory "$@" ;;
    list)      garc_people_list "$@" ;;
    show)      garc_people_show "$@" ;;
    create)    garc_people_create "$@" ;;
    update)    garc_people_update "$@" ;;
    delete)    garc_people_delete "$@" ;;
    lookup)    garc_people_lookup "$@" ;;
    *)
      cat <<EOF
Usage: garc people <subcommand> [options]

Subcommands:
  search    <query>                       Search personal contacts
  directory <query>                       Search GWS org directory
  list      [--max N] [--format json]    List all personal contacts
  show      <contact_id>                 Show contact details
  create    --name <name> [--email] [--phone] [--company] [--title] [--notes]
  update    <contact_id> [--name] [--email] [--phone] [--company] [--title]
  delete    <contact_id>
  lookup    <name>                        Quick: find email for a name

Examples:
  garc people search "Alice"
  garc people directory "engineering"
  garc people lookup "Bob Smith"
  garc people create --name "Jane Doe" --email jane@co.com --company "Acme Corp"
  garc people update abc123 --title "Senior Engineer"
EOF
      return 1
      ;;
  esac
}

garc_people_search() {
  local query="" max=20 format="table"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --max|-n) max="$2"; shift 2 ;;
      --format|-f) format="$2"; shift 2 ;;
      *) query="${query:+${query} }$1"; shift ;;
    esac
  done
  [[ -z "${query}" ]] && { echo "Usage: garc people search <query>"; return 1; }
  python3 "${PEOPLE_HELPER}" --format "${format}" search "${query}" --max "${max}"
}

garc_people_directory() {
  local query="" max=20 format="table"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --max|-n) max="$2"; shift 2 ;;
      --format|-f) format="$2"; shift 2 ;;
      *) query="${query:+${query} }$1"; shift ;;
    esac
  done
  [[ -z "${query}" ]] && { echo "Usage: garc people directory <query>"; return 1; }
  python3 "${PEOPLE_HELPER}" --format "${format}" directory "${query}" --max "${max}"
}

garc_people_list() {
  local max=50 format="table"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --max|-n) max="$2"; shift 2 ;;
      --format|-f) format="$2"; shift 2 ;;
      *) shift ;;
    esac
  done
  python3 "${PEOPLE_HELPER}" --format "${format}" list --max "${max}"
}

garc_people_show() {
  local contact_id="${1:-}"
  [[ -z "${contact_id}" ]] && { echo "Usage: garc people show <contact_id>"; return 1; }
  python3 "${PEOPLE_HELPER}" show "${contact_id}"
}

garc_people_create() {
  local name="" email="" phone="" company="" title="" notes=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --name) name="$2"; shift 2 ;;
      --email) email="$2"; shift 2 ;;
      --phone) phone="$2"; shift 2 ;;
      --company) company="$2"; shift 2 ;;
      --title) title="$2"; shift 2 ;;
      --notes) notes="$2"; shift 2 ;;
      *) shift ;;
    esac
  done
  [[ -z "${name}" ]] && { echo "Usage: garc people create --name <name> [--email] [--phone] [--company] [--title]"; return 1; }

  python3 "${PEOPLE_HELPER}" create \
    --name "${name}" \
    ${email:+--email "${email}"} \
    ${phone:+--phone "${phone}"} \
    ${company:+--company "${company}"} \
    ${title:+--title "${title}"} \
    ${notes:+--notes "${notes}"}
}

garc_people_update() {
  local contact_id="${1:-}"
  shift || true
  local name="" email="" phone="" company="" title=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --name) name="$2"; shift 2 ;;
      --email) email="$2"; shift 2 ;;
      --phone) phone="$2"; shift 2 ;;
      --company) company="$2"; shift 2 ;;
      --title) title="$2"; shift 2 ;;
      *) shift ;;
    esac
  done
  [[ -z "${contact_id}" ]] && { echo "Usage: garc people update <contact_id> [--name] [--email] [--phone] [--company] [--title]"; return 1; }

  python3 "${PEOPLE_HELPER}" update "${contact_id}" \
    ${name:+--name "${name}"} \
    ${email:+--email "${email}"} \
    ${phone:+--phone "${phone}"} \
    ${company:+--company "${company}"} \
    ${title:+--title "${title}"}
}

garc_people_delete() {
  local contact_id="${1:-}"
  [[ -z "${contact_id}" ]] && { echo "Usage: garc people delete <contact_id>"; return 1; }
  echo "Delete contact ${contact_id}? [y/N]"
  read -r confirm
  [[ "${confirm}" != "y" ]] && echo "Cancelled." && return 0
  python3 "${PEOPLE_HELPER}" delete "${contact_id}"
}

garc_people_lookup() {
  local query="$*"
  [[ -z "${query}" ]] && { echo "Usage: garc people lookup <name>"; return 1; }
  python3 "${PEOPLE_HELPER}" lookup "${query}"
}
