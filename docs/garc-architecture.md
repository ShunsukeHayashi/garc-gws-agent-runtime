# GARC Architecture

## System Overview

```
Upper-layer agent (Claude Code / OpenClaw)
  ↓ garc commands
GARC CLI (bin/garc + lib/*.sh)
  ↓ Python helpers (scripts/*.py)
Google Workspace APIs
  ├── Google Drive (disclosure chain, knowledge graph)
  ├── Google Sheets (memory, agent registry, queue, approval)
  ├── Gmail (messaging, approval notifications)
  ├── Google Calendar (calendar operations)
  ├── Google Tasks (task management)
  └── Google Chat (optional Chat messaging)
```

## Layer 1: Disclosure Chain (Google Drive)

Agent context is loaded from a Google Drive folder at bootstrap:

```
Google Drive Folder (GARC_DRIVE_FOLDER_ID)
  ├── SOUL.md          → Agent identity & principles
  ├── USER.md          → User profile & preferences
  ├── MEMORY.md        → Memory index (pointer to Sheets)
  ├── RULES.md         → Operating rules & constraints
  ├── HEARTBEAT.md     → Latest system state
  └── memory/
        └── YYYY-MM-DD.md   → Daily context notes

Downloaded to: ~/.garc/cache/workspace/<agent_id>/
Consolidated:  ~/.garc/cache/workspace/<agent_id>/AGENT_CONTEXT.md
```

### Bootstrap Flow

```
garc bootstrap --agent main
  ↓ Drive API: search for each file in folder
  ↓ Download to ~/.garc/cache/workspace/main/
  ↓ Build AGENT_CONTEXT.md (concatenation)
  → Agent has full context
```

## Layer 2: Structured Data (Google Sheets)

One Google Sheets spreadsheet holds all GARC operational data:

| Tab | Schema | Purpose |
|-----|--------|---------|
| `memory` | agent_id, timestamp, entry, source | Long-term memory |
| `agents` | id, model, scopes, description, status, registered_at | Agent registry |
| `queue` | queue_id, agent_id, message, status, gate, created_at | Task queue |
| `heartbeat` | agent_id, timestamp, status, notes, platform | System state log |
| `approval` | approval_id, agent_id, task, status, created_at, resolved_at | Approval flow |

### Initial Sheet Setup

Run `garc init` to provision the spreadsheet with the above tabs and headers.

## Layer 3: Permission Intelligence

The scope inference engine (`scripts/garc-auth-helper.py`) maps natural-language tasks to minimum OAuth scopes:

```
Input: "send expense report to manager and create calendar reminder"
  ↓ keyword matching against config/scope-map.json
Output:
  Matched tasks: [send_email, create_expense, write_calendar]
  Scopes: [gmail.send, spreadsheets, drive.file, calendar]
  Gate: approval (highest tier from matched tasks)
  Identity: user_access_token
```

### Scope Map Structure

```json
{
  "tasks": {
    "<task_type>": {
      "scopes": ["https://www.googleapis.com/auth/<scope>"],
      "identity": "user_access_token | bot_access_token",
      "gate": "none | preview | approval",
      "description": "..."
    }
  },
  "profiles": {
    "readonly | writer | admin | backoffice_agent": {
      "scopes": [...],
      "description": "..."
    }
  },
  "keyword_patterns": {
    "<task_type>": ["keyword1", "keyword2", ...]
  }
}
```

## Layer 4: Execution Gates

Before any GARC action, the gate policy is checked:

```
garc approve gate <task_type>

none     → ✅ Execute immediately (read-only ops)
preview  → ⚠️  Add --confirm flag (writes with external visibility)
approval → 🔒 Create approval request, wait for human
```

### Gate Flow

```
Agent wants to execute task
  ↓ garc approve gate <task_type>
  ↓ Check config/gate-policy.json

[none]    → Proceed
[preview] → Show preview, require --confirm
            If --confirm given → Proceed
            Else → Abort
[approval] → garc approve create "<task>"
             → Append to Sheets "approval" tab
             → Send Gmail notification to GARC_GMAIL_DEFAULT_TO
             → Block execution until status = "approved"
             → garc ingress approve <queue_id>
             → Resume execution
```

## Layer 5: Agent Registry

Agents are declared in `agents.yaml` and registered to the Sheets `agents` tab:

```yaml
agents:
  - id: main
    model: claude-sonnet-4-6
    scopes: [drive.file, gmail.send, ...]
    profile: backoffice_agent
```

```bash
garc agent register --file agents.yaml
# → Upsert rows to Sheets "agents" tab
```

The registry enables delegation: the upper-layer agent can query which registered agent has the right scopes for a given task, then dispatch to it.

## Layer 6: Queue / Ingress

The queue bridges incoming requests (manual or Gmail-triggered) to governed execution:

```
Incoming request (manual command / Gmail webhook)
  ↓ garc ingress enqueue "<message>"
  → ~/.garc/cache/queue/<id>.jsonl  (local JSONL)
  → Also upsert to Sheets "queue" tab (optional)

garc ingress next
  → Returns oldest "pending" item

garc ingress run-once
  ↓ Claim item (status → in_progress)
  ↓ garc approve gate <inferred_gate>
  [none]    → Build context bundle → dispatch to upper agent
  [preview] → Ask for confirmation
  [approval] → Create approval → block
```

### Queue Item Schema

```jsonl
{"queue_id":"abc123","message":"...","status":"pending","gate":"preview","source":"manual","created_at":"2026-04-15T10:00:00Z","agent":"main"}
```

## Layer 7: Knowledge Graph (Google Docs)

Google Docs files in the Drive workspace folder are indexed as knowledge nodes:

```
garc kg build
  ↓ Drive API: list all Docs in workspace folder
  ↓ Export each Doc as plain text
  ↓ Extract Google Doc links from content
  → ~/.garc/cache/knowledge-graph.json

garc kg query "expense approval"
  → Search titles and content previews
  → Return matching nodes + link neighbors
```

## MCP Integration (Claude Code)

When GARC is used from Claude Code, the MCP tools can be used directly as an alternative to the Python helpers:

| Operation | GARC Command | Claude Code MCP |
|-----------|-------------|-----------------|
| Authenticate Gmail | `garc auth login` | `mcp__claude_ai_Gmail__authenticate` |
| Authenticate Drive | `garc auth login` | `mcp__claude_ai_Google_Drive__authenticate` |
| Authenticate Calendar | `garc auth login` | `mcp__claude_ai_Google_Calendar__authenticate` |

The MCP tools provide richer interactive authentication while the CLI helpers work better in automated/headless contexts.

## Security Model

### Principle of Least Privilege

`garc auth suggest` always infers the **minimum** scopes needed for a task. Agents should use the suggested scopes rather than a broad profile unless the broader profile is genuinely needed.

### Gate Policy Enforcement

Gate policies are stored in `config/gate-policy.json` (local) and cannot be overridden at runtime. To change a policy, you must edit the file and restart.

### Token Storage

Tokens are stored in `~/.garc/token.json`. This file should be:
- Readable only by the owner (`chmod 600`)
- Never committed to version control
- Added to `.gitignore`

### Service Account vs User Token

| Scenario | Recommended |
|----------|-------------|
| Automated/headless agent | Service account |
| User-facing agent (acts as user) | OAuth2 user token |
| Mixed (read as bot, write as user) | Both configured |
