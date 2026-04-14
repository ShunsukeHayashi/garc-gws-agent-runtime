# GARC — Google Workspace Agent Runtime CLI

A permission-first runtime for AI agents operating on Google Workspace.

GARC lets Claude Code (or any LLM agent) send emails, manage calendars, read Drive files, write Sheets, and manage tasks — with built-in **execution gates** that prevent accidental or unauthorized actions.

```
You / Claude Code
      ↓
   GARC CLI          ← permission check, queue, context
      ↓
Google Workspace APIs (Gmail · Calendar · Drive · Sheets · Tasks · People)
```

## Core concepts

| Concept | What it does |
|---------|-------------|
| **`auth suggest`** | Infers minimum OAuth scopes from a natural-language task description |
| **Execution gates** | `none` (read-only) / `preview` (writes, confirm first) / `approval` (financial/irreversible, requires human sign-off) |
| **Disclosure chain** | `SOUL.md → USER.md → MEMORY.md → RULES.md → HEARTBEAT.md` stored in Google Drive, loaded on bootstrap |
| **Queue / ingress** | Task lifecycle (`pending → in_progress → done/failed`), Gmail polling daemon auto-enqueues new emails |
| **Agent registry** | Agent declarations (id, model, scopes) stored in Google Sheets |
| **Memory sync** | Long-term memory round-trip with a dedicated Google Sheets tab |

## Quickstart

### 1. Install

```bash
git clone https://github.com/<owner>/garc-gws-agent-runtime ~/study/garc-gws-agent-runtime
cd ~/study/garc-gws-agent-runtime
pip3 install -r requirements.txt
echo 'export PATH="$HOME/study/garc-gws-agent-runtime/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
garc --version   # → garc 0.1.0
```

### 2. Enable Google Cloud APIs

In [Google Cloud Console](https://console.cloud.google.com/), enable:

| API | Service name |
|-----|-------------|
| Google Drive API | `drive.googleapis.com` |
| Google Sheets API | `sheets.googleapis.com` |
| Gmail API | `gmail.googleapis.com` |
| Google Calendar API | `calendar-json.googleapis.com` |
| Google Tasks API | `tasks.googleapis.com` |
| Google Docs API | `docs.googleapis.com` |
| Google People API | `people.googleapis.com` |

Create an **OAuth 2.0 Client ID** (Desktop app) → download JSON → save as `~/.garc/credentials.json`.

See [`docs/google-cloud-setup.md`](docs/google-cloud-setup.md) for step-by-step instructions.

### 3. Authenticate

```bash
garc auth login --profile backoffice_agent
# Opens browser → Google login → authorize all scopes
garc auth status
```

### 4. Provision workspace

```bash
garc setup all
# Creates GARC Workspace folder in Google Drive
# Creates Google Sheets with all tabs (memory/agents/queue/heartbeat/approval/…)
# Uploads disclosure chain templates to Drive
# Writes IDs to ~/.garc/config.env
```

### 5. Verify

```bash
garc status
garc bootstrap --agent main
```

## Usage

### Gmail

```bash
garc gmail inbox --unread
garc gmail search "from:alice@co.com subject:invoice" --max 10
garc gmail send --to boss@co.com --subject "Weekly report" --body "..."
garc gmail read <message_id>
```

### Google Calendar

```bash
garc calendar today
garc calendar week
garc calendar create --summary "Team meeting" \
  --start "2026-04-20T14:00:00" --end "2026-04-20T15:00:00" \
  --attendees alice@co.com bob@co.com --timezone "Asia/Tokyo"
garc calendar freebusy --start 2026-04-20 --end 2026-04-21 --emails alice@co.com
```

### Google Drive

```bash
garc drive list
garc drive search "Q1 report" --type doc
garc drive upload ./report.pdf
garc drive create-doc "Meeting Notes 2026-04-20"
garc drive download --file-id 1xxxxx --output ./local.txt
```

### Google Sheets

```bash
garc sheets info
garc sheets read --range "memory!A:E" --format json
garc sheets append --sheet memory --values '["main","2026-04-20","key decision","manual",""]'
```

### Tasks & Contacts

```bash
garc task list
garc task create "Write Q1 report" --due 2026-04-30
garc people lookup "Alice Smith"
garc people directory "engineering"
```

### Queue / Ingress (Claude Code bridge)

```bash
# Enqueue a task
garc ingress enqueue --text "Send weekly report to manager@co.com"

# Show queue
garc ingress list

# Output a Claude-readable execution prompt → Claude Code acts on this
garc ingress run-once

# Mark complete
garc ingress done --queue-id abc12345 --note "Report sent"
```

### Daemon — auto-enqueue from Gmail

```bash
garc daemon start --interval 60    # poll every 60s
garc daemon status
garc daemon stop
garc daemon install                 # install as macOS launchd service
```

### Scope & gate inference

```bash
garc auth suggest "create expense report and send to manager for approval"
# → gate: approval  scopes: spreadsheets + drive.file + gmail.send

garc approve gate create_expense
garc approve list
garc approve act <id> --action approve
```

## Architecture

```
~/.garc/
  credentials.json      # OAuth client credentials (Google Cloud Console)
  token.json            # OAuth user token (garc auth login)
  config.env            # GARC_DRIVE_FOLDER_ID, GARC_SHEETS_ID, …
  cache/
    workspace/<agent>/
      SOUL.md / USER.md / MEMORY.md / RULES.md / HEARTBEAT.md
      AGENT_CONTEXT.md   # consolidated bootstrap context
    queue/               # JSONL queue files
    daemon/              # PID files
    logs/                # daemon logs
```

### Execution gates

| Gate | Risk | Behaviour |
|------|------|-----------|
| `none` | Low — reads | Execute immediately |
| `preview` | Medium — external writes | Show plan, confirm first |
| `approval` | High — financial / irreversible | Create approval request, block until approved |

## Repository layout

```
bin/garc                    CLI entrypoint
lib/
  bootstrap.sh              disclosure chain
  gmail.sh / calendar.sh / drive.sh / sheets.sh / task.sh / people.sh
  memory.sh / ingress.sh / daemon.sh / agent.sh / approve.sh
  auth.sh / heartbeat.sh / kg.sh
scripts/
  garc-core.py              shared auth, retry, utilities
  garc-ingress-helper.py    task inference + Claude prompt builder
  garc-gmail-helper.py / garc-calendar-helper.py / garc-drive-helper.py
  garc-sheets-helper.py / garc-tasks-helper.py / garc-people-helper.py
  garc-auth-helper.py       OAuth scope inference engine
  garc-setup.py             workspace provisioner
config/
  scope-map.json            42 task types × OAuth scopes × keyword patterns
  gate-policy.json          gate assignments
  config.env.example
agents.yaml                 agent declarations
docs/
  quickstart.md / google-cloud-setup.md / garc-architecture.md / garc-vs-larc.md
.claude/skills/garc-runtime/SKILL.md   Claude Code skill
```

## Relation to LARC

GARC mirrors [LARC](https://github.com/miyabi-lab/larc-openclaw-coding-agent) — the same governance model running on Google Workspace instead of Lark/Feishu.

| LARC (Lark) | GARC (Google Workspace) |
|-------------|------------------------|
| Lark Drive | Google Drive |
| Lark Base | Google Sheets |
| Lark IM / Mail | Gmail |
| Lark Approval | Sheets-based approval flow |
| Lark Calendar | Google Calendar |
| Lark Task | Google Tasks |
| `lark-cli` | Google APIs (Python) |
| OpenClaw agent | Claude Code |

## License

MIT
