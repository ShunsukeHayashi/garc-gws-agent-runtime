#!/usr/bin/env bash
# GARC kg.sh — Knowledge graph via Google Docs
# Google Docs replaces Lark Wiki as the knowledge graph surface

GARC_KG_CACHE="${GARC_CACHE_DIR:-${HOME}/.garc/cache}/knowledge-graph.json"
KG_QUERY_HELPER="${GARC_DIR}/scripts/garc-kg-query.py"

garc_kg() {
  local subcommand="${1:-help}"
  shift || true

  case "${subcommand}" in
    build) garc_kg_build "$@" ;;
    query) garc_kg_query "$@" ;;
    show)  garc_kg_show "$@" ;;
    *)
      cat <<EOF
Usage: garc kg <subcommand>

Subcommands:
  build   [--folder-id <id>] [--depth <N>]   Build KG index from Drive Docs
  query   "<keyword>" [--max <N>]             Search knowledge graph
  show    <doc_id>                            Show doc metadata and links
EOF
      return 1
      ;;
  esac
}

# garc kg build
garc_kg_build() {
  local folder_id="${GARC_DRIVE_FOLDER_ID:-}"
  local depth=3

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --folder-id|-f) folder_id="$2"; shift 2 ;;
      --depth|-d) depth="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  if [[ -z "${folder_id}" ]]; then
    echo "Error: GARC_DRIVE_FOLDER_ID not set. Use --folder-id or run 'garc setup all'." >&2
    return 1
  fi

  local cache_dir
  cache_dir="$(dirname "${GARC_KG_CACHE}")"
  mkdir -p "${cache_dir}"

  echo "Building knowledge graph from Google Drive folder: ${folder_id}"

  python3 "${GARC_DIR}/scripts/garc-drive-helper.py" kg-build \
    --folder-id "${folder_id}" \
    --output "${GARC_KG_CACHE}" \
    --depth "${depth}"

  if [[ -f "${GARC_KG_CACHE}" ]]; then
    local count
    count=$(python3 -c "import json; d=json.load(open('${GARC_KG_CACHE}')); print(d.get('node_count', 0))" 2>/dev/null || echo "?")
    echo "✅ Knowledge graph built: ${count} docs → ${GARC_KG_CACHE}"
  fi
}

# garc kg query "<concept>"
garc_kg_query() {
  local max=10
  local terms=()

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --max|-n) max="$2"; shift 2 ;;
      *) terms+=("$1"); shift ;;
    esac
  done

  local query="${terms[*]:-}"
  if [[ -z "${query}" ]]; then
    echo "Usage: garc kg query \"<concept>\" [--max N]"
    return 1
  fi

  if [[ ! -f "${GARC_KG_CACHE}" ]]; then
    echo "Knowledge graph not built. Run: garc kg build"
    return 1
  fi

  # Pass query via argv to avoid shell injection
  python3 "${GARC_DIR}/scripts/garc-kg-query.py" query \
    --cache "${GARC_KG_CACHE}" \
    --query "${query}" \
    --max "${max}"
}

# garc kg show <doc_id>
garc_kg_show() {
  local doc_id="${1:-}"

  if [[ -z "${doc_id}" ]]; then
    echo "Usage: garc kg show <doc_id>"
    return 1
  fi

  if [[ ! -f "${GARC_KG_CACHE}" ]]; then
    echo "Knowledge graph not built. Run: garc kg build"
    return 1
  fi

  python3 "${GARC_DIR}/scripts/garc-kg-query.py" show \
    --cache "${GARC_KG_CACHE}" \
    --doc-id "${doc_id}"
}
