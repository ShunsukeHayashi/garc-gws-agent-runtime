#!/usr/bin/env python3
"""
GARC Sheets Helper — Full Google Sheets operations
read / write / append / search / clear / format
+ memory/agent/queue/heartbeat/approval operations
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))
from garc_core import build_service, utc_now, with_retry

SHEET_MEMORY = "memory"
SHEET_AGENTS = "agents"
SHEET_QUEUE = "queue"
SHEET_HEARTBEAT = "heartbeat"
SHEET_APPROVAL = "approval"
SHEET_TASKS_LOG = "tasks_log"
SHEET_EMAIL_LOG = "email_log"
SHEET_CALENDAR_LOG = "calendar_log"


def get_svc():
    return build_service("sheets", "v4")


# ─── Generic operations ───────────────────────────────────────────────────────

@with_retry()
def read_range(sheets_id: str, range_: str, output_format: str = "table"):
    """Read data from a Sheets range."""
    svc = get_svc()
    result = svc.spreadsheets().values().get(
        spreadsheetId=sheets_id, range=range_,
        valueRenderOption="FORMATTED_VALUE"
    ).execute()
    rows = result.get("values", [])

    if not rows:
        print(f"(empty: {range_})")
        return []

    if output_format == "json":
        if len(rows) > 1:
            headers = rows[0]
            data = [dict(zip(headers, row + [""] * (len(headers) - len(row)))) for row in rows[1:]]
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        # Table format
        widths = [max(len(str(rows[r][c])) if c < len(rows[r]) else 0
                      for r in range(len(rows))) for c in range(len(rows[0]))]
        widths = [min(w, 40) for w in widths]
        for i, row in enumerate(rows):
            line = "  ".join(str(row[c] if c < len(row) else "").ljust(widths[c])[:widths[c]]
                             for c in range(len(rows[0])))
            print(line)
            if i == 0:
                print("  ".join("─" * widths[c] for c in range(len(rows[0]))))

    return rows


@with_retry()
def write_range(sheets_id: str, range_: str, values: list):
    """Write data to a Sheets range (overwrites)."""
    svc = get_svc()
    result = svc.spreadsheets().values().update(
        spreadsheetId=sheets_id,
        range=range_,
        valueInputOption="USER_ENTERED",
        body={"values": values}
    ).execute()
    print(f"✅ Written {result.get('updatedCells', 0)} cells to {range_}")
    return result


@with_retry()
def append_row(sheets_id: str, sheet_name: str, values: list):
    """Append a row to a sheet."""
    svc = get_svc()
    result = svc.spreadsheets().values().append(
        spreadsheetId=sheets_id,
        range=f"{sheet_name}!A:Z",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [values]}
    ).execute()
    print(f"✅ Row appended to {sheet_name}")
    return result


@with_retry()
def search_sheet(sheets_id: str, sheet_name: str, query: str,
                 column: int = -1, output_format: str = "table"):
    """Search rows in a sheet by keyword."""
    svc = get_svc()
    result = svc.spreadsheets().values().get(
        spreadsheetId=sheets_id, range=f"{sheet_name}!A:Z"
    ).execute()
    rows = result.get("values", [])

    if not rows:
        print(f"(empty: {sheet_name})")
        return []

    query_lower = query.lower()
    matches = []
    headers = rows[0] if rows else []

    for row in rows[1:]:
        if column >= 0:
            check = str(row[column] if column < len(row) else "").lower()
        else:
            check = " ".join(str(cell) for cell in row).lower()
        if query_lower in check:
            matches.append(row)

    if not matches:
        print(f"No results for '{query}' in {sheet_name}")
        return []

    print(f"Found {len(matches)} rows in {sheet_name}:")
    if headers and output_format == "table":
        widths = [min(max(len(str(h)), max((len(str(r[i] if i < len(r) else "")) for r in matches), default=0)), 30)
                  for i, h in enumerate(headers)]
        print("  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
        print("  ".join("─" * widths[i] for i in range(len(headers))))
        for row in matches:
            print("  ".join(str(row[i] if i < len(row) else "").ljust(widths[i])[:widths[i]]
                            for i in range(len(headers))))
    elif output_format == "json":
        if headers:
            data = [dict(zip(headers, r + [""] * (len(headers) - len(r)))) for r in matches]
            print(json.dumps(data, ensure_ascii=False, indent=2))

    return matches


@with_retry()
def get_sheet_info(sheets_id: str):
    """Get spreadsheet metadata."""
    svc = get_svc()
    meta = svc.spreadsheets().get(spreadsheetId=sheets_id).execute()

    print(f"Title: {meta['properties']['title']}")
    print(f"ID:    {sheets_id}")
    print(f"URL:   https://docs.google.com/spreadsheets/d/{sheets_id}")
    print()
    print(f"Sheets ({len(meta.get('sheets', []))}):")
    for s in meta.get("sheets", []):
        props = s["properties"]
        gp = props.get("gridProperties", {})
        print(f"  [{props['sheetId']:<6}] {props['title']:<20} {gp.get('rowCount', 0):>6} rows × {gp.get('columnCount', 0):>3} cols")
    return meta


@with_retry()
def clear_range(sheets_id: str, range_: str):
    """Clear a range (but keep headers)."""
    svc = get_svc()
    svc.spreadsheets().values().clear(spreadsheetId=sheets_id, range=range_).execute()
    print(f"✅ Cleared: {range_}")


# ─── GARC-specific operations ─────────────────────────────────────────────────

@with_retry()
def memory_pull(sheets_id: str, agent_id: str, output: str):
    svc = get_svc()
    result = svc.spreadsheets().values().get(
        spreadsheetId=sheets_id, range=f"{SHEET_MEMORY}!A:E"
    ).execute()
    rows = result.get("values", [])
    headers = rows[0] if rows else []

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w") as f:
        f.write(f"# Memory — {agent_id} — {today}\n\n")
        for row in rows[1:]:
            if not row:
                continue
            row_agent = row[0] if len(row) > 0 else ""
            if row_agent and row_agent != agent_id:
                continue
            ts = row[1] if len(row) > 1 else ""
            entry = row[2] if len(row) > 2 else ""
            tags = row[4] if len(row) > 4 else ""
            tag_str = f"  `{tags}`" if tags else ""
            f.write(f"## {ts[:10] if ts else 'N/A'}{tag_str}\n{entry}\n\n")

    count = sum(1 for r in rows[1:] if r and (not r[0] or r[0] == agent_id))
    print(f"✅ Memory pulled: {count} entries → {output}")


@with_retry()
def memory_push(sheets_id: str, agent_id: str, entry: str, timestamp: str, tags: str = ""):
    append_row(sheets_id, SHEET_MEMORY, [agent_id, timestamp, entry, "manual", tags])


@with_retry()
def memory_search(sheets_id: str, query: str):
    search_sheet(sheets_id, SHEET_MEMORY, query)


@with_retry()
def agent_list(sheets_id: str):
    read_range(sheets_id, f"{SHEET_AGENTS}!A:H")


@with_retry()
def agent_register(sheets_id: str, yaml_file: str):
    try:
        import yaml
        with open(yaml_file) as f:
            config = yaml.safe_load(f)
    except ImportError:
        print("⚠️  PyYAML not installed. Install: pip install pyyaml")
        return

    agents = config.get("agents", [])
    ts = utc_now()
    for agent in agents:
        scopes = ",".join(agent.get("scopes", []))
        append_row(sheets_id, SHEET_AGENTS, [
            agent.get("id", ""),
            agent.get("model", ""),
            scopes,
            agent.get("description", ""),
            agent.get("profile", ""),
            "active",
            agent.get("drive_folder", ""),
            ts
        ])
    print(f"✅ Registered {len(agents)} agents")


@with_retry()
def agent_show(sheets_id: str, agent_id: str):
    search_sheet(sheets_id, SHEET_AGENTS, agent_id, column=0)


@with_retry()
def heartbeat(sheets_id: str, agent_id: str, status: str, notes: str, timestamp: str, context_file: str = ""):
    append_row(sheets_id, SHEET_HEARTBEAT, [agent_id, timestamp, status, notes, "google-workspace", context_file])


@with_retry()
def approval_list(sheets_id: str):
    svc = get_svc()
    result = svc.spreadsheets().values().get(
        spreadsheetId=sheets_id, range=f"{SHEET_APPROVAL}!A:H"
    ).execute()
    rows = result.get("values", [])
    headers = rows[0] if rows else []

    pending = [r for r in rows[1:] if len(r) > 3 and r[3] == "pending"]
    if not pending:
        print("No pending approvals.")
        return

    print(f"Pending approvals ({len(pending)}):")
    for row in pending:
        print(f"  🔒 [{row[0][:12]}] {row[2] if len(row) > 2 else ''}")
        print(f"       Agent: {row[1] if len(row) > 1 else ''}  Created: {(row[4] if len(row) > 4 else '')[:16]}")


@with_retry()
def approval_create(sheets_id: str, approval_id: str, task: str, agent_id: str, timestamp: str):
    append_row(sheets_id, SHEET_APPROVAL, [approval_id, agent_id, task, "pending", timestamp, "", "", ""])
    print(f"✅ Approval created: {approval_id}")


@with_retry()
def approval_act(sheets_id: str, approval_id: str, action: str, timestamp: str):
    svc = get_svc()
    result = svc.spreadsheets().values().get(
        spreadsheetId=sheets_id, range=f"{SHEET_APPROVAL}!A:H"
    ).execute()
    rows = result.get("values", [])

    for i, row in enumerate(rows):
        if row and row[0] == approval_id:
            row_num = i + 1
            svc.spreadsheets().values().update(
                spreadsheetId=sheets_id,
                range=f"{SHEET_APPROVAL}!D{row_num}:F{row_num}",
                valueInputOption="RAW",
                body={"values": [[action, timestamp, ""]]}
            ).execute()
            print(f"✅ Approval {approval_id[:12]} → {action}")
            return
    print(f"Approval not found: {approval_id}")


def main():
    parser = argparse.ArgumentParser(description="GARC Sheets Helper")
    sub = parser.add_subparsers(dest="command")

    # Generic
    rp = sub.add_parser("read", help="Read range")
    rp.add_argument("--sheets-id", required=True)
    rp.add_argument("--range", required=True, dest="range_")
    rp.add_argument("--format", default="table", choices=["table", "json"])

    wp = sub.add_parser("write", help="Write range")
    wp.add_argument("--sheets-id", required=True)
    wp.add_argument("--range", required=True, dest="range_")
    wp.add_argument("--values", required=True, help="JSON array of arrays")

    ap = sub.add_parser("append", help="Append row")
    ap.add_argument("--sheets-id", required=True)
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--values", required=True, help="JSON array")

    sep = sub.add_parser("search", help="Search rows")
    sep.add_argument("--sheets-id", required=True)
    sep.add_argument("--sheet", required=True)
    sep.add_argument("--query", required=True)
    sep.add_argument("--column", type=int, default=-1)
    sep.add_argument("--format", default="table", choices=["table", "json"])

    infop = sub.add_parser("info", help="Get spreadsheet info")
    infop.add_argument("--sheets-id", required=True)

    clp = sub.add_parser("clear", help="Clear range")
    clp.add_argument("--sheets-id", required=True)
    clp.add_argument("--range", required=True, dest="range_")

    # GARC-specific
    mpl = sub.add_parser("memory-pull")
    mpl.add_argument("--sheets-id", required=True)
    mpl.add_argument("--agent-id", required=True)
    mpl.add_argument("--output", required=True)

    mpu = sub.add_parser("memory-push")
    mpu.add_argument("--sheets-id", required=True)
    mpu.add_argument("--agent-id", required=True)
    mpu.add_argument("--entry", required=True)
    mpu.add_argument("--timestamp", required=True)
    mpu.add_argument("--tags", default="")

    ms = sub.add_parser("memory-search")
    ms.add_argument("--sheets-id", required=True)
    ms.add_argument("--query", required=True)

    al = sub.add_parser("agent-list")
    al.add_argument("--sheets-id", required=True)

    ar = sub.add_parser("agent-register")
    ar.add_argument("--sheets-id", required=True)
    ar.add_argument("--yaml-file", required=True)

    ash = sub.add_parser("agent-show")
    ash.add_argument("--sheets-id", required=True)
    ash.add_argument("--agent-id", required=True)

    hb = sub.add_parser("heartbeat")
    hb.add_argument("--sheets-id", required=True)
    hb.add_argument("--agent-id", required=True)
    hb.add_argument("--status", required=True)
    hb.add_argument("--notes", default="")
    hb.add_argument("--timestamp", required=True)
    hb.add_argument("--context-file", default="")

    apl = sub.add_parser("approval-list")
    apl.add_argument("--sheets-id", required=True)

    apc = sub.add_parser("approval-create")
    apc.add_argument("--sheets-id", required=True)
    apc.add_argument("--approval-id", required=True)
    apc.add_argument("--task", required=True)
    apc.add_argument("--agent-id", required=True)
    apc.add_argument("--timestamp", required=True)

    apa = sub.add_parser("approval-act")
    apa.add_argument("--sheets-id", required=True)
    apa.add_argument("--approval-id", required=True)
    apa.add_argument("--action", required=True)
    apa.add_argument("--timestamp", required=True)

    args = parser.parse_args()

    if args.command == "read":
        read_range(args.sheets_id, args.range_, args.format)
    elif args.command == "write":
        write_range(args.sheets_id, args.range_, json.loads(args.values))
    elif args.command == "append":
        append_row(args.sheets_id, args.sheet, json.loads(args.values))
    elif args.command == "search":
        search_sheet(args.sheets_id, args.sheet, args.query, args.column, args.format)
    elif args.command == "info":
        get_sheet_info(args.sheets_id)
    elif args.command == "clear":
        clear_range(args.sheets_id, args.range_)
    elif args.command == "memory-pull":
        memory_pull(args.sheets_id, args.agent_id, args.output)
    elif args.command == "memory-push":
        memory_push(args.sheets_id, args.agent_id, args.entry, args.timestamp, args.tags)
    elif args.command == "memory-search":
        memory_search(args.sheets_id, args.query)
    elif args.command == "agent-list":
        agent_list(args.sheets_id)
    elif args.command == "agent-register":
        agent_register(args.sheets_id, args.yaml_file)
    elif args.command == "agent-show":
        agent_show(args.sheets_id, args.agent_id)
    elif args.command == "heartbeat":
        heartbeat(args.sheets_id, args.agent_id, args.status, args.notes,
                  args.timestamp, args.context_file)
    elif args.command == "approval-list":
        approval_list(args.sheets_id)
    elif args.command == "approval-create":
        approval_create(args.sheets_id, args.approval_id, args.task, args.agent_id, args.timestamp)
    elif args.command == "approval-act":
        approval_act(args.sheets_id, args.approval_id, args.action, args.timestamp)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
