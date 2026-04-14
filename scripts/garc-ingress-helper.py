#!/usr/bin/env python3
"""
GARC Ingress Helper — Queue payload builder + Claude Code execution bridge

Commands:
  build-payload  --text <msg> [--source <src>] [--sender <email>] [--agent <id>]
  execute-stub   --queue-file <path>
  build-prompt   --queue-file <path> [--agent-context <path>]
  stats          --queue-dir <path>
"""

import argparse
import json
import os
import sys
import hashlib
import time
from pathlib import Path
from datetime import datetime, timezone

GARC_DIR = Path(__file__).parent.parent
SCOPE_MAP_PATH = GARC_DIR / "config" / "scope-map.json"
GATE_POLICY_PATH = GARC_DIR / "config" / "gate-policy.json"

# ─────────────────────────────────────────────────────────────────
# Task type → GARC CLI tool mapping
# This is the GWS equivalent of LARC's TASK_OPENCLAW_TOOLS
# ─────────────────────────────────────────────────────────────────

TASK_GARC_TOOLS: dict[str, list[str]] = {
    "send_email":         ["garc gmail send --to <recipient> --subject <subject> --body <body>"],
    "reply_email":        ["garc gmail search <query>", "garc gmail read <message_id>", "garc gmail send --to <sender> --subject <Re: subject> --body <body>"],
    "read_email":         ["garc gmail inbox --unread", "garc gmail search <query>", "garc gmail read <message_id>"],
    "search_email":       ["garc gmail search <query> --max 10"],
    "draft_email":        ["garc gmail draft --to <recipient> --subject <subject> --body <body>"],
    "read_document":      ["garc drive search <query>", "garc drive download --file-id <id> --output /tmp/doc.txt"],
    "create_document":    ["garc drive create-doc <title>", "garc drive upload <path>"],
    "update_document":    ["garc drive download --file-id <id>", "# edit locally", "garc drive upload <path>"],
    "search_document":    ["garc drive search <query> --type doc"],
    "read_spreadsheet":   ["garc sheets read --range <Sheet!A:Z>", "garc sheets search --sheet <name> --query <text>"],
    "write_spreadsheet":  ["garc sheets append --sheet <name> --values '[\"v1\",\"v2\"]'", "garc sheets write --range <A1> --values '[[...]]'"],
    "read_calendar":      ["garc calendar today", "garc calendar list --days <N>", "garc calendar list --query <keyword>"],
    "create_event":       ["garc calendar freebusy --start <date> --end <date> --emails <attendees>", "garc calendar create --summary <title> --start <dt> --end <dt> --attendees <emails>"],
    "update_event":       ["garc calendar list --query <keyword>", "garc calendar update <event_id> --summary <new_title>"],
    "delete_event":       ["garc calendar list --query <keyword>", "garc calendar delete <event_id>"],
    "check_availability": ["garc calendar freebusy --start <date> --end <date> --emails <emails>"],
    "create_task":        ["garc task create \"<title>\" --due <YYYY-MM-DD> --notes <notes>"],
    "update_task":        ["garc task list", "garc task update <task_id> --due <date>"],
    "complete_task":      ["garc task list", "garc task done <task_id>"],
    "read_tasks":         ["garc task list", "garc task list --completed"],
    "upload_file":        ["garc drive upload <local_path> --folder-id <id>"],
    "download_file":      ["garc drive search <query>", "garc drive download --file-id <id> --output <path>"],
    "share_file":         ["garc drive share <file_id> --email <email> --role writer"],
    "create_folder":      ["garc drive create-folder <name>"],
    "search_contact":     ["garc people search <name>", "garc people lookup <name>"],
    "read_contact":       ["garc people show <contact_id>"],
    "create_contact":     ["garc people create --name <name> --email <email> --company <company>"],
    "write_memory":       ["garc memory push \"<entry>\""],
    "read_memory":        ["garc memory search <query>", "garc memory pull"],
    "create_expense":     ["garc sheets append --sheet approval --values '[\"expense\",\"<amount>\",\"<desc>\",\"pending\"]'", "garc approve create \"expense: <description>\"", "garc gmail send --to <approver> --subject \"[GARC] Expense Approval Required\""],
    "submit_approval":    ["garc approve create \"<task description>\"", "garc approve list"],
    "read_approval":      ["garc approve list"],
    "register_agent":     ["garc agent register", "garc agent list"],
    "read_agent":         ["garc agent list", "garc agent show <agent_id>"],
}

# Task description templates for execute-stub output
TASK_PLANS: dict[str, str] = {
    "send_email":         "Compose and send an email to the target recipient(s).",
    "reply_email":        "Find the original email thread and compose a reply.",
    "read_email":         "Search and read relevant emails from Gmail.",
    "search_email":       "Search Gmail for emails matching the criteria.",
    "draft_email":        "Prepare an email draft without sending.",
    "read_document":      "Search for and read the target document from Google Drive.",
    "create_document":    "Create a new document or file in Google Drive.",
    "update_document":    "Download, modify, and re-upload the target document.",
    "search_document":    "Search Google Drive for documents matching the criteria.",
    "read_spreadsheet":   "Read data from the target Google Sheet.",
    "write_spreadsheet":  "Write or append data to the target Google Sheet.",
    "read_calendar":      "Retrieve calendar events for the specified time range.",
    "create_event":       "Check availability and create a calendar event.",
    "update_event":       "Find and update the target calendar event.",
    "delete_event":       "Find and delete the target calendar event.",
    "check_availability": "Query free/busy status for the specified attendees.",
    "create_task":        "Create a new task in Google Tasks.",
    "update_task":        "Find and update the target task.",
    "complete_task":      "Find and mark the target task as completed.",
    "read_tasks":         "List current Google Tasks.",
    "upload_file":        "Upload a local file to Google Drive.",
    "download_file":      "Search for and download a file from Google Drive.",
    "share_file":         "Share a Google Drive file with the specified user.",
    "create_folder":      "Create a new folder in Google Drive.",
    "search_contact":     "Search Google Contacts for the specified person.",
    "read_contact":       "Get full contact details.",
    "create_contact":     "Create a new contact in Google People.",
    "write_memory":       "Save an important context entry to agent memory (Google Sheets).",
    "read_memory":        "Search or sync agent memory from Google Sheets.",
    "create_expense":     "Prepare expense record, create approval request, and notify approver.",
    "submit_approval":    "Create an approval request and notify the approver via Gmail.",
    "read_approval":      "List pending approval requests.",
    "register_agent":     "Register a new agent in the GARC agent registry.",
    "read_agent":         "List or show agent details from the registry.",
}


# ─────────────────────────────────────────────────────────────────
# Payload builder
# ─────────────────────────────────────────────────────────────────

def load_scope_map() -> dict:
    if not SCOPE_MAP_PATH.exists():
        return {}
    with open(SCOPE_MAP_PATH) as f:
        return json.load(f)


def load_gate_policy() -> dict:
    if not GATE_POLICY_PATH.exists():
        return {}
    with open(GATE_POLICY_PATH) as f:
        return json.load(f)


def infer_task_types(text: str, scope_map: dict) -> list[str]:
    """Match text against scope-map keyword patterns."""
    text_lower = text.lower()
    matched = []
    # scope-map.json uses "keyword_patterns" key
    patterns = scope_map.get("keyword_patterns", scope_map.get("patterns", {}))
    for task_type, keywords in patterns.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                if task_type not in matched:
                    matched.append(task_type)
                break
    return matched if matched else []  # empty = unknown, caller decides fallback


def infer_gate(task_types: list[str], gate_policy: dict) -> str:
    """Return the highest-risk gate for the given task types."""
    gates = gate_policy.get("gates", {})
    highest = "none"
    order = ["none", "preview", "approval"]
    for task in task_types:
        for gate_name, gate_data in gates.items():
            if task in gate_data.get("tasks", []):
                if order.index(gate_name) > order.index(highest):
                    highest = gate_name
    return highest


def infer_scopes(task_types: list[str], scope_map: dict) -> list[str]:
    """Collect all OAuth scopes needed for the task types."""
    tasks = scope_map.get("tasks", {})
    scopes: set[str] = set()
    for task in task_types:
        if task in tasks:
            scopes.update(tasks[task].get("scopes", []))
    return sorted(scopes)


def build_queue_id(text: str) -> str:
    digest = hashlib.sha256(f"{text}{time.time()}".encode()).hexdigest()
    return digest[:8]


def build_payload(text: str, source: str = "manual", sender: str = "", agent: str = "main") -> dict:
    scope_map = load_scope_map()
    gate_policy = load_gate_policy()

    task_types = infer_task_types(text, scope_map)
    gate = infer_gate(task_types, gate_policy)
    scopes = infer_scopes(task_types, scope_map)

    # authority: who is sending this request
    authority = "human_operator" if source == "manual" else "gmail_trigger"

    return {
        "queue_id": build_queue_id(text),
        "message_text": text,
        "source": source,
        "sender": sender,
        "agent_id": agent,
        "task_types": task_types,
        "scopes": scopes,
        "gate": gate,
        "authority": authority,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": None,
        "approval_id": None,
        "session_id": None,
        "note": "",
    }


def cmd_build_payload(args):
    payload = build_payload(args.text, args.source, args.sender, args.agent)

    print()
    print("  Queue item preview")
    print(f"    queue_id:   {payload['queue_id']}")
    print(f"    agent_id:   {payload['agent_id']}")
    print(f"    source:     {payload['source']}")
    print(f"    sender:     {payload['sender'] or '-'}")
    print(f"    task_types: {', '.join(payload['task_types']) if payload['task_types'] else '(none matched)'}")
    print(f"    scopes:     {len(payload['scopes'])} scope(s)")
    print(f"    gate:       {payload['gate']}")
    print(f"    status:     {payload['status']}")
    print()
    print(f"Queued: {payload['queue_id']}")
    print(f"  status: {payload['status']}")
    print(f"  gate:   {payload['gate']}")
    print(f"  tasks:  {', '.join(payload['task_types']) if payload['task_types'] else '(none matched)'}")

    return payload


# ─────────────────────────────────────────────────────────────────
# Execute stub — maps queue item to execution plan
# ─────────────────────────────────────────────────────────────────

def cmd_execute_stub(args):
    """Generate an execution plan from a queue item."""
    queue_file = Path(args.queue_file)
    if not queue_file.exists():
        print(f"Error: queue file not found: {queue_file}", file=sys.stderr)
        sys.exit(1)

    with open(queue_file) as f:
        q = json.loads(f.readline().strip())

    task_types = q.get("task_types", [])
    message = q.get("message_text", q.get("message", ""))
    queue_id = q.get("queue_id", "")
    gate = q.get("gate", "preview")
    agent_id = q.get("agent_id", q.get("agent", "main"))

    print()
    print("=" * 60)
    print("GARC Execution Stub")
    print("=" * 60)
    print(f"Queue ID:   {queue_id}")
    print(f"Agent:      {agent_id}")
    print(f"Gate:       {gate}")
    print(f"Task types: {', '.join(task_types) if task_types else '(generic)'}")
    print()
    print("Task:")
    print(f"  {message}")
    print()

    # Step-by-step plan
    print("Execution plan:")
    print("-" * 40)
    step = 1
    seen_tools: set[str] = set()
    for task in task_types:
        plan = TASK_PLANS.get(task, f"Execute {task} operation.")
        tools = TASK_GARC_TOOLS.get(task, [])
        print(f"[Step {step}] {plan}")
        for tool in tools:
            if tool not in seen_tools:
                print(f"  → {tool}")
                seen_tools.add(tool)
        step += 1
        print()

    if not task_types:
        print("[Step 1] Execute the requested task using available GARC tools.")
        print("  → garc gmail send / garc drive search / garc sheets read / ...")
        print()

    print("-" * 40)
    print("When complete, run:")
    print(f"  garc ingress done --queue-id {queue_id} --note \"<what was done>\"")
    print(f"  (or: garc ingress fail --queue-id {queue_id} --note \"<reason>\")")


# ─────────────────────────────────────────────────────────────────
# Build prompt — Claude Code readable output
# ─────────────────────────────────────────────────────────────────

def cmd_build_prompt(args):
    """Build a Claude Code–ready prompt from a queue item."""
    queue_file = Path(args.queue_file)
    if not queue_file.exists():
        print(f"Error: queue file not found: {queue_file}", file=sys.stderr)
        sys.exit(1)

    with open(queue_file) as f:
        q = json.loads(f.readline().strip())

    task_types = q.get("task_types", [])
    message = q.get("message_text", q.get("message", ""))
    queue_id = q.get("queue_id", "")
    gate = q.get("gate", "preview")
    agent_id = q.get("agent_id", q.get("agent", "main"))
    source = q.get("source", "manual")
    sender = q.get("sender", "")

    # Collect suggested commands
    suggested_cmds: list[str] = []
    for task in task_types:
        for cmd in TASK_GARC_TOOLS.get(task, []):
            if cmd not in suggested_cmds:
                suggested_cmds.append(cmd)

    # Build prompt
    lines = [
        "## GARC Task",
        "",
        f"**Queue ID**: `{queue_id}`  ",
        f"**Gate**: `{gate}`  ",
        f"**Source**: {source}" + (f" (from: {sender})" if sender else ""),
        "",
        "### Task description",
        "",
        message,
        "",
    ]

    if task_types:
        lines += [
            "### Inferred task types",
            "",
            "  " + ", ".join(f"`{t}`" for t in task_types),
            "",
        ]

    if suggested_cmds:
        lines += [
            "### Suggested GARC commands",
            "",
        ]
        for cmd in suggested_cmds[:10]:
            lines.append(f"  ```bash\n  {cmd}\n  ```")
        lines.append("")

    # Gate guidance
    if gate == "approval":
        lines += [
            "### ⚠️ Approval required",
            "",
            "This task requires human approval before execution.",
            f"  ```bash\n  garc approve create \"{message[:60]}\"\n  ```",
            "",
        ]
    elif gate == "preview":
        lines += [
            "### ⚠️ Preview gate",
            "",
            "Confirm the plan with the user before executing write operations.",
            "",
        ]

    # Agent context excerpt
    context_path = args.agent_context if hasattr(args, "agent_context") and args.agent_context else None
    if not context_path:
        garc_cache = Path.home() / ".garc" / "cache"
        context_path = str(garc_cache / "workspace" / agent_id / "AGENT_CONTEXT.md")

    if context_path and Path(context_path).exists():
        with open(context_path) as f:
            context_lines = f.readlines()[:30]
        lines += [
            "### Agent context (excerpt)",
            "```",
        ] + [l.rstrip() for l in context_lines] + [
            "```",
            "",
        ]

    lines += [
        "### After execution",
        "",
        f"```bash",
        f"garc ingress done --queue-id {queue_id} --note \"<what was done>\"",
        f"# or on failure:",
        f"garc ingress fail --queue-id {queue_id} --note \"<reason>\"",
        f"```",
    ]

    print("\n".join(lines))


# ─────────────────────────────────────────────────────────────────
# Stats
# ─────────────────────────────────────────────────────────────────

def cmd_stats(args):
    queue_dir = Path(args.queue_dir)
    if not queue_dir.exists():
        print("Queue directory not found.")
        return

    counts: dict[str, int] = {}
    total = 0
    for f in queue_dir.glob("*.jsonl"):
        try:
            q = json.loads(f.read_text().splitlines()[0])
            status = q.get("status", "unknown")
            counts[status] = counts.get(status, 0) + 1
            total += 1
        except Exception:
            continue

    print(f"Queue stats (total: {total}):")
    for status in ["pending", "in_progress", "blocked", "done", "failed"]:
        icon = {"pending": "⏳", "in_progress": "🔄", "blocked": "🔒", "done": "✅", "failed": "❌"}.get(status, "❓")
        print(f"  {icon} {status:<14} {counts.get(status, 0)}")


# ─────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GARC Ingress Helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # build-payload
    bp = subparsers.add_parser("build-payload")
    bp.add_argument("--text", required=True)
    bp.add_argument("--source", default="manual")
    bp.add_argument("--sender", default="")
    bp.add_argument("--agent", default="main")

    # execute-stub
    es = subparsers.add_parser("execute-stub")
    es.add_argument("--queue-file", required=True)

    # build-prompt
    pr = subparsers.add_parser("build-prompt")
    pr.add_argument("--queue-file", required=True)
    pr.add_argument("--agent-context", default="")

    # stats
    st = subparsers.add_parser("stats")
    st.add_argument("--queue-dir", required=True)

    args = parser.parse_args()

    if args.command == "build-payload":
        cmd_build_payload(args)
    elif args.command == "execute-stub":
        cmd_execute_stub(args)
    elif args.command == "build-prompt":
        cmd_build_prompt(args)
    elif args.command == "stats":
        cmd_stats(args)


if __name__ == "__main__":
    main()
