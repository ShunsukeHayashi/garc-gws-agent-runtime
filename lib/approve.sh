#!/usr/bin/env bash
# GARC approve.sh — Execution gate and approval flow
# Uses Google Sheets as the approval tracking backend

GATE_POLICY="${GARC_DIR}/config/gate-policy.json"

garc_approve() {
  local subcommand="${1:-help}"
  shift || true

  case "${subcommand}" in
    gate)   garc_approve_gate "$@" ;;
    list)   garc_approve_list "$@" ;;
    create) garc_approve_create "$@" ;;
    act)    garc_approve_act "$@" ;;
    *)
      echo "Usage: garc approve <gate|list|create|act>"
      return 1
      ;;
  esac
}

# garc approve gate <task_type>
# Check the execution gate policy for a task type
garc_approve_gate() {
  local task_type="${1:-}"

  if [[ -z "${task_type}" ]]; then
    echo "Usage: garc approve gate <task_type>"
    echo ""
    echo "Available task types:"
    python3 -c "
import json, sys
with open('${GATE_POLICY}') as f:
    policy = json.load(f)
for gate, data in policy['gates'].items():
    print(f'  [{gate.upper()}] {data[\"description\"]}')
    for t in data['tasks']:
        print(f'    - {t}')
"
    return 0
  fi

  python3 -c "
import json, sys
with open('${GATE_POLICY}') as f:
    policy = json.load(f)

task = '${task_type}'
for gate_name, gate_data in policy['gates'].items():
    if task in gate_data['tasks']:
        icons = {'none': '✅', 'preview': '⚠️', 'approval': '🔒'}
        icon = icons.get(gate_name, '❓')
        print(f'{icon} Gate: {gate_name.upper()}')
        print(f'   {gate_data[\"description\"]}')
        if gate_name == 'none':
            print(f'   Action: Execute immediately')
        elif gate_name == 'preview':
            print(f'   Action: Add --confirm flag or get user acknowledgment')
        else:
            print(f'   Action: Create approval request with: garc approve create \"{task}\"')
        sys.exit(0)

print(f'Task type \"{task}\" not found in gate policy')
sys.exit(1)
"
}

# garc approve list
# List pending approval items from Google Sheets
garc_approve_list() {
  local sheets_id="${GARC_SHEETS_ID:-}"
  if [[ -z "${sheets_id}" ]]; then
    echo "Error: GARC_SHEETS_ID not set" >&2
    return 1
  fi

  python3 "${GARC_DIR}/scripts/garc-sheets-helper.py" approval-list \
    --sheets-id "${sheets_id}"
}

# garc approve create "<task>"
# Create an approval request in Google Sheets (and optionally send Gmail)
garc_approve_create() {
  local task_description="$*"

  if [[ -z "${task_description}" ]]; then
    echo "Usage: garc approve create \"<task description>\""
    return 1
  fi

  local sheets_id="${GARC_SHEETS_ID:-}"
  if [[ -z "${sheets_id}" ]]; then
    echo "Error: GARC_SHEETS_ID not set" >&2
    return 1
  fi

  local approval_id
  approval_id="approval-$(date +%Y%m%d%H%M%S)-$$"

  echo "Creating approval request..."
  echo "  ID: ${approval_id}"
  echo "  Task: ${task_description}"

  python3 "${GARC_DIR}/scripts/garc-sheets-helper.py" approval-create \
    --sheets-id "${sheets_id}" \
    --approval-id "${approval_id}" \
    --task "${task_description}" \
    --agent-id "${GARC_DEFAULT_AGENT:-main}" \
    --timestamp "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

  # Optionally notify via Gmail
  if [[ -n "${GARC_GMAIL_DEFAULT_TO:-}" ]]; then
    python3 "${GARC_DIR}/scripts/garc-gmail-helper.py" send \
      --to "${GARC_GMAIL_DEFAULT_TO}" \
      --subject "[GARC Approval Required] ${task_description}" \
      --body "Approval Request ID: ${approval_id}
Task: ${task_description}
Agent: ${GARC_DEFAULT_AGENT:-main}
Time: $(date -u +"%Y-%m-%dT%H:%M:%SZ")

To approve: garc approve act ${approval_id} --action approve
To reject:  garc approve act ${approval_id} --action reject" 2>/dev/null || true
  fi

  echo "✅ Approval request created: ${approval_id}"
  echo "   Waiting for human approval..."
}

# garc approve act <id> --action <approve|reject>
garc_approve_act() {
  local approval_id="${1:-}"
  local action=""

  shift || true
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --action) action="$2"; shift 2 ;;
      approve|reject) action="$1"; shift ;;
      *) shift ;;
    esac
  done

  if [[ -z "${approval_id}" ]] || [[ -z "${action}" ]]; then
    echo "Usage: garc approve act <id> --action <approve|reject>"
    return 1
  fi

  python3 "${GARC_DIR}/scripts/garc-sheets-helper.py" approval-act \
    --sheets-id "${GARC_SHEETS_ID:-}" \
    --approval-id "${approval_id}" \
    --action "${action}" \
    --timestamp "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

  echo "✅ Approval ${approval_id} marked as: ${action}"
}
