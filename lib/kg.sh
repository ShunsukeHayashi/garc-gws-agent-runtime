#!/usr/bin/env bash
# GARC kg.sh — Knowledge graph via Google Docs
# Google Docs replaces Lark Wiki as the knowledge graph surface

GARC_KG_CACHE="${GARC_CACHE_DIR:-${HOME}/.garc/cache}/knowledge-graph.json"

garc_kg() {
  local subcommand="${1:-help}"
  shift || true

  case "${subcommand}" in
    build) garc_kg_build "$@" ;;
    query) garc_kg_query "$@" ;;
    show)  garc_kg_show "$@" ;;
    *)
      echo "Usage: garc kg <build|query|show>"
      return 1
      ;;
  esac
}

# garc kg build
# Crawls Google Drive folder and builds knowledge graph from Docs
garc_kg_build() {
  local folder_id="${GARC_DRIVE_FOLDER_ID:-}"

  if [[ -z "${folder_id}" ]]; then
    echo "Error: GARC_DRIVE_FOLDER_ID not set" >&2
    return 1
  fi

  echo "Building knowledge graph from Google Drive folder: ${folder_id}"

  python3 "${GARC_DIR}/scripts/garc-drive-helper.py" kg-build \
    --folder-id "${folder_id}" \
    --output "${GARC_KG_CACHE}"

  echo "✅ Knowledge graph built: ${GARC_KG_CACHE}"
}

# garc kg query "<concept>"
garc_kg_query() {
  local query="$*"

  if [[ -z "${query}" ]]; then
    echo "Usage: garc kg query \"<concept>\""
    return 1
  fi

  if [[ ! -f "${GARC_KG_CACHE}" ]]; then
    echo "Knowledge graph not built. Run: garc kg build"
    return 1
  fi

  python3 -c "
import json, sys
query = '${query}'.lower()
with open('${GARC_KG_CACHE}') as f:
    kg = json.load(f)

matches = []
for node in kg.get('nodes', []):
    name = node.get('title', '').lower()
    content = node.get('content_preview', '').lower()
    if query in name or query in content:
        matches.append(node)

if not matches:
    print(f'No results for: ${query}')
    sys.exit(0)

print(f'Results for \"{query}\" ({len(matches)} matches):')
for m in matches[:10]:
    print(f'  - [{m.get(\"doc_id\",\"\")}] {m.get(\"title\",\"\")}')
    if m.get('content_preview'):
        preview = m['content_preview'][:100].replace('\n', ' ')
        print(f'    {preview}...')
    links = m.get('links', [])
    if links:
        print(f'    Links: {len(links)} documents')
"
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

  python3 -c "
import json
doc_id = '${doc_id}'
with open('${GARC_KG_CACHE}') as f:
    kg = json.load(f)

for node in kg.get('nodes', []):
    if node.get('doc_id') == doc_id:
        print(f'Title: {node.get(\"title\", \"\")}')
        print(f'Doc ID: {doc_id}')
        print(f'Type: {node.get(\"mime_type\", \"\")}')
        print(f'Modified: {node.get(\"modified_time\", \"\")}')
        print()
        print('Content preview:')
        print(node.get('content_preview', '(none)'))
        print()
        links = node.get('links', [])
        if links:
            print(f'Links ({len(links)}):')
            for link in links:
                print(f'  -> {link}')
        break
else:
    print(f'Document {doc_id} not found in knowledge graph')
"
}
