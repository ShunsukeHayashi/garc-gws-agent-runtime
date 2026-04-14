# GARC Changelog

## [0.1.0] — 2026-04-15

### Added

- `bin/garc` — Main CLI entrypoint with full command dispatch
- `lib/bootstrap.sh` — Disclosure chain loading from Google Drive (SOUL/USER/MEMORY/RULES/HEARTBEAT)
- `lib/auth.sh` — OAuth scope inference and authorization flow
- `lib/memory.sh` — Google Sheets memory sync (pull/push/search)
- `lib/send.sh` — Gmail and Google Chat message sending
- `lib/agent.sh` — Agent registry via Google Sheets
- `lib/task.sh` — Google Tasks operations (list/create/done)
- `lib/approve.sh` — Execution gate and approval flow
- `lib/heartbeat.sh` — System state logging to Google Sheets
- `lib/kg.sh` — Knowledge graph via Google Drive Docs
- `lib/ingress.sh` — Queue/ingress system with JSONL local cache
- `scripts/garc-auth-helper.py` — OAuth2 scope inference + token management
- `scripts/garc-sheets-helper.py` — Google Sheets CRUD operations
- `scripts/garc-drive-helper.py` — Google Drive file operations + KG builder
- `scripts/garc-gmail-helper.py` — Gmail send operations
- `scripts/garc-tasks-helper.py` — Google Tasks operations
- `scripts/setup-workspace.sh` — One-shot workspace provisioning
- `config/scope-map.json` — 25 task types × Google OAuth scopes × 4 profiles
- `config/gate-policy.json` — Execution gate policies (none/preview/approval)
- `config/config.env.example` — Configuration template
- `agents.yaml` — Default agent declarations (main/crm-agent/doc-agent/expense-processor)
- `docs/garc-architecture.md` — Full architecture reference
- `docs/garc-vs-larc.md` — GARC vs LARC comparison
- `docs/gws-api-alignment.md` — GWS API command mappings
