#!/usr/bin/env bash
# GARC profile.sh — Multi-tenant profile management
#
# Profiles live at: ~/.garc/profiles/<name>/
#   config.env       — tenant-specific env vars (GARC_DRIVE_FOLDER_ID, GARC_SHEETS_ID, ...)
#   token.json       — OAuth token for this tenant
#   credentials.json — OAuth client credentials (optional; falls back to ~/.garc/credentials.json)
#
# Usage:
#   garc profile list               List all profiles
#   garc profile use <name>         Switch active profile (sets GARC_PROFILE)
#   garc profile add <name>         Create a new profile directory
#   garc profile show [<name>]      Show profile config
#   garc profile remove <name>      Delete a profile
#   garc profile current            Show current active profile

GARC_PROFILES_DIR="${GARC_CONFIG:-${HOME}/.garc}/profiles"

garc_profile() {
  local subcommand="${1:-list}"
  shift || true

  case "${subcommand}" in
    list)    _profile_list ;;
    use)     _profile_use "$@" ;;
    add)     _profile_add "$@" ;;
    show)    _profile_show "$@" ;;
    remove)  _profile_remove "$@" ;;
    current) _profile_current ;;
    *)
      cat <<EOF
Usage: garc profile <subcommand>

Subcommands:
  list              List all configured profiles
  use <name>        Print shell command to activate a profile
  add <name>        Create a new empty profile directory
  show [<name>]     Show the config for a profile (default: current)
  remove <name>     Delete a profile (prompts for confirmation)
  current           Show the currently active profile name

How to use:
  # Add profile-specific config to ~/.garc/profiles/<name>/config.env
  # Then activate with:
  eval "\$(garc profile use <name>)"
  # Or export directly:
  export GARC_PROFILE=<name>

Profile config.env example:
  GARC_DRIVE_FOLDER_ID=1xxxxxx
  GARC_SHEETS_ID=1xxxxxx
  GARC_GMAIL_DEFAULT_TO=user@example.com
  GARC_DEFAULT_AGENT=main
EOF
      return 1
      ;;
  esac
}

_profile_list() {
  if [[ ! -d "${GARC_PROFILES_DIR}" ]]; then
    echo "No profiles configured. Create one with: garc profile add <name>"
    return 0
  fi

  local current="${GARC_PROFILE:-}"
  echo "Profiles (dir: ${GARC_PROFILES_DIR}):"
  echo ""
  local found=0
  for dir in "${GARC_PROFILES_DIR}"/*/; do
    [[ -d "${dir}" ]] || continue
    local name
    name="$(basename "${dir}")"
    local marker=""
    [[ "${name}" == "${current}" ]] && marker=" ◀ active"
    local has_token=""
    [[ -f "${dir}/token.json" ]] && has_token=" [authenticated]"
    local has_config=""
    [[ -f "${dir}/config.env" ]] && has_config=" [configured]"
    echo "  ${name}${marker}${has_token}${has_config}"
    found=1
  done
  [[ ${found} -eq 0 ]] && echo "  (none)"
}

_profile_current() {
  if [[ -n "${GARC_PROFILE:-}" ]]; then
    echo "${GARC_PROFILE}"
  else
    echo "(no profile active — using ~/.garc/config.env)"
  fi
}

_profile_use() {
  local name="${1:-}"
  if [[ -z "${name}" ]]; then
    echo "Usage: garc profile use <name>"
    return 1
  fi

  local profile_dir="${GARC_PROFILES_DIR}/${name}"
  if [[ ! -d "${profile_dir}" ]]; then
    echo "Profile '${name}' not found. Create it with: garc profile add ${name}"
    return 1
  fi

  # Output shell export commands so caller can eval them
  echo "export GARC_PROFILE=${name}"
  if [[ -f "${profile_dir}/config.env" ]]; then
    # Read each line and export
    while IFS= read -r line || [[ -n "${line}" ]]; do
      # Skip comments and empty lines
      [[ "${line}" =~ ^[[:space:]]*# ]] && continue
      [[ -z "${line// }" ]] && continue
      echo "export ${line}"
    done < "${profile_dir}/config.env"
  fi
  if [[ -f "${profile_dir}/token.json" ]]; then
    echo "export GARC_TOKEN_FILE=${profile_dir}/token.json"
  fi
  if [[ -f "${profile_dir}/credentials.json" ]]; then
    echo "export GARC_CREDENTIALS_FILE=${profile_dir}/credentials.json"
  fi

  # Print hint to stderr so it doesn't get eval'd
  echo "# Activated profile: ${name}" >&2
  echo "# Run: eval \"\$(garc profile use ${name})\"" >&2
}

_profile_add() {
  local name="${1:-}"
  if [[ -z "${name}" ]]; then
    echo "Usage: garc profile add <name>"
    return 1
  fi

  local profile_dir="${GARC_PROFILES_DIR}/${name}"
  if [[ -d "${profile_dir}" ]]; then
    echo "Profile '${name}' already exists: ${profile_dir}"
    return 0
  fi

  mkdir -p "${profile_dir}"

  cat > "${profile_dir}/config.env" <<EOF
# Profile: ${name}
# Fill in your tenant-specific values

GARC_DRIVE_FOLDER_ID=1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GARC_SHEETS_ID=1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GARC_GMAIL_DEFAULT_TO=you@example.com
GARC_DEFAULT_AGENT=main
# GARC_CHAT_SPACE_ID=spaces/xxxxxxxx
# GARC_APPROVAL_EMAIL=approver@example.com
EOF

  echo "✅ Profile created: ${profile_dir}"
  echo ""
  echo "Next steps:"
  echo "  1. Edit: ${profile_dir}/config.env"
  echo "  2. Login: GARC_TOKEN_FILE=${profile_dir}/token.json garc auth login"
  echo "  3. Activate: eval \"\$(garc profile use ${name})\""
}

_profile_show() {
  local name="${1:-${GARC_PROFILE:-}}"
  if [[ -z "${name}" ]]; then
    echo "Usage: garc profile show <name>"
    echo "       (or set GARC_PROFILE to use current profile)"
    return 1
  fi

  local profile_dir="${GARC_PROFILES_DIR}/${name}"
  if [[ ! -d "${profile_dir}" ]]; then
    echo "Profile '${name}' not found."
    return 1
  fi

  echo "Profile: ${name}"
  echo "Path:    ${profile_dir}"
  echo ""
  if [[ -f "${profile_dir}/config.env" ]]; then
    echo "config.env:"
    grep -v '^#' "${profile_dir}/config.env" | grep -v '^[[:space:]]*$' \
      | sed 's/^/  /'
  else
    echo "  (no config.env)"
  fi
  echo ""
  echo "Files:"
  [[ -f "${profile_dir}/token.json" ]]       && echo "  ✅ token.json (authenticated)"        || echo "  ⬜ token.json (not authenticated)"
  [[ -f "${profile_dir}/credentials.json" ]] && echo "  ✅ credentials.json"                   || echo "  ⬜ credentials.json (using default)"
  [[ -f "${profile_dir}/service_account.json" ]] && echo "  ✅ service_account.json"
}

_profile_remove() {
  local name="${1:-}"
  if [[ -z "${name}" ]]; then
    echo "Usage: garc profile remove <name>"
    return 1
  fi

  local profile_dir="${GARC_PROFILES_DIR}/${name}"
  if [[ ! -d "${profile_dir}" ]]; then
    echo "Profile '${name}' not found."
    return 1
  fi

  echo "Remove profile '${name}'? This deletes: ${profile_dir} [y/N]"
  read -r confirm
  [[ "${confirm}" != "y" ]] && echo "Cancelled." && return 0

  rm -rf "${profile_dir}"
  echo "✅ Profile '${name}' removed."
}
