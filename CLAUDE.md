# GARC — Google Workspace Agent Runtime CLI

> Claude Code context file for this project.

## Project Summary

**GARC** bridges OpenClaw-style coding agents with Google Workspace — enabling AI agents to operate on back-office and white-collar tasks using Google Drive, Sheets, Gmail, Calendar, and Tasks as the native data surface.

GARC is the Google Workspace counterpart to LARC (Lark Agent Runtime CLI). It reproduces the same architecture:

- **Core pattern**: Disclosure chain (`SOUL.md → USER.md → MEMORY.md → HEARTBEAT.md`) backed by Google Drive
- **Permission-first**: `garc auth suggest "<task>"` → keyword matching against `config/scope-map.json` → required OAuth scopes + identity type
- **Target market**: Organizations using Google Workspace (Gmail, Drive, Sheets, Calendar, Chat)

## Repository Structure

```
bin/garc                    # Main CLI entrypoint (bash)
lib/
  bootstrap.sh              # Disclosure chain loading from Google Drive
  memory.sh                 # Daily memory sync ↔ Google Sheets
  send.sh                   # Gmail / Google Chat message sending
  agent.sh                  # Agent registration & management (Sheets)
  task.sh                   # Google Tasks operations
  approve.sh                # Approval gate logic
  heartbeat.sh              # System state logging to Sheets
  auth.sh                   # OAuth scope inference & authorization
  drive.sh                  # Google Drive file operations
config/
  scope-map.json            # GWS OAuth scopes × task types × profiles
  gate-policy.json          # Execution gate policies (none/preview/approval)
scripts/
  setup-workspace.sh        # One-shot workspace provisioning
  garc-auth-helper.py       # OAuth2 token management helper
docs/
  garc-architecture.md      # Full architecture reference
  garc-vs-larc.md           # GARC vs LARC comparison
  gws-api-alignment.md      # GWS API command mappings
.claude/skills/             # Claude Code skills for GWS operations
```

## GWS → LARC Mapping

| LARC (Lark) | GARC (Google Workspace) |
|-------------|------------------------|
| Lark Drive folder | Google Drive folder |
| Lark Base | Google Sheets |
| Lark IM chat | Gmail / Google Chat |
| Lark Wiki | Google Docs (knowledge) |
| Lark Approval | Google Forms + Sheets approval flow |
| Lark Calendar | Google Calendar |
| Lark Task/Project | Google Tasks |
| `lark-cli` | `gcloud` + Google APIs |
| MCP (Lark) | MCP (Gmail/Drive/Calendar) |

## Key Architecture Decisions

### Google API Access Layer

GARC uses two access methods:

1. **Claude Code MCP tools** (preferred for interactive use):
   - `mcp__claude_ai_Gmail__*` — email operations
   - `mcp__claude_ai_Google_Drive__*` — Drive file ops
   - `mcp__claude_ai_Google_Calendar__*` — calendar ops

2. **Python googleapis client** (for CLI/automation):
   - `google-api-python-client` + `google-auth-oauthlib`
   - Service account for bot operations
   - OAuth2 user tokens for user-identity operations

### Disclosure Chain Storage

```
Google Drive folder (GARC_DRIVE_FOLDER_ID)
  └── SOUL.md         → agent identity & principles
  └── USER.md         → user profile
  └── MEMORY.md       → long-term memory
  └── RULES.md        → operating rules
  └── HEARTBEAT.md    → system state
  └── memory/
        └── YYYY-MM-DD.md  → daily context

Downloaded to: ~/.garc/cache/workspace/<agent_id>/
Consolidated:  ~/.garc/cache/workspace/<agent_id>/AGENT_CONTEXT.md
```

### Memory Backend (Google Sheets)

Google Sheets replaces Lark Base for structured data:

| Sheet Tab | Purpose | LARC Equivalent |
|-----------|---------|-----------------|
| `memory` | Long-term memory entries | Base memory table |
| `agents` | Agent registry (id, model, scopes) | Base agent ledger |
| `queue` | Task queue lifecycle | Base queue ledger |
| `heartbeat` | System state log | Base heartbeat table |
| `approval` | Approval instances | Lark Approval |

### Scope Map (`config/scope-map.json`)

Structure mirrors LARC's scope-map.json but uses Google OAuth scopes:

```json
{
  "tasks": {
    "read_document": {
      "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
      "identity": "user_access_token",
      "description": "Read Google Drive files"
    }
  },
  "profiles": {
    "readonly": { "scopes": [...], "description": "..." },
    "writer": { "scopes": [...], "description": "..." },
    "admin": { "scopes": [...], "description": "..." },
    "backoffice_agent": { "scopes": [...], "description": "..." }
  }
}
```

### Execution Gates

Same 3-tier gate policy as LARC:

```
none     → read-only ops (immediate execution)
preview  → medium risk (external visibility, writes) → --confirm flag required
approval → high risk (money, permissions, irreversible) → approval gate
```

## Config (`~/.garc/config.env`)

```bash
GARC_DRIVE_FOLDER_ID=1xxxxx          # Google Drive folder for agent workspace
GARC_SHEETS_ID=1xxxxx                # Google Sheets for memory/registry/queue
GARC_GMAIL_DEFAULT_TO=xxx@gmail.com  # Default email recipient (agent notifications)
GARC_CHAT_SPACE_ID=spaces/xxx        # Google Chat space ID
GARC_CALENDAR_ID=primary             # Google Calendar ID
GARC_CACHE_TTL=300                   # Cache TTL in seconds
GARC_CREDENTIALS_FILE=~/.garc/credentials.json  # OAuth2 client credentials
GARC_TOKEN_FILE=~/.garc/token.json              # OAuth2 user tokens
GARC_SERVICE_ACCOUNT_FILE=~/.garc/service_account.json  # Service account (bot)
```

## Common Commands

```bash
# Setup
garc init
garc bootstrap --agent main

# Daily use
garc memory pull
garc send "Draft an expense report for last month"
garc task list

# Permission management
garc auth suggest "create expense report and send for approval"
garc auth check --profile writer
garc auth login --profile backoffice_agent

# Agent management
garc agent list
garc agent register

# Knowledge graph
garc kg build
garc kg query "expense approval process"
```

## Development Phases

- [ ] Phase 1A: Core CLI dispatch (`garc init/bootstrap/memory/send/task/approve/agent/status`)
- [ ] Phase 1B: Drive workspace setup + Sheets provisioning
- [ ] Phase 1C: OAuth scope map + `garc auth suggest/check/login`
- [ ] Phase 2A: Claude Code skills for GWS operations
- [ ] Phase 2B: Multi-agent YAML batch registration
- [ ] Phase 3: Queue/ingress system (Gmail-triggered)
- [ ] Phase 4: Knowledge graph via Google Docs links

## Relation to LARC

GARC is intentionally parallel to LARC, not a replacement. Organizations using:
- **Feishu/Lark** → use LARC
- **Google Workspace** → use GARC
- **Both** → deploy both runtimes; agents registered in one can be mirrored to the other

The runtime governance model (permission intelligence, execution gates, disclosure chain) is identical. Only the backend APIs differ.
