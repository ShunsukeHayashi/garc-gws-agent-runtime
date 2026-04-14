#!/usr/bin/env python3
"""
GARC Tasks Helper — Google Tasks operations
Supports multiple task lists, create/read/update/complete/delete
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))
from garc_core import build_service, utc_now, with_retry


def get_service():
    scopes = ["https://www.googleapis.com/auth/tasks"]
    return build_service("tasks", "v1", scopes=scopes)


# ─────────────────────────────────────────────
# Task Lists
# ─────────────────────────────────────────────

@with_retry()
def list_tasklists():
    """List all task lists."""
    service = get_service()
    result = service.tasklists().list(maxResults=100).execute()
    lists = result.get("items", [])

    if not lists:
        print("No task lists found.")
        return

    print(f"Task Lists ({len(lists)}):")
    for tl in lists:
        print(f"  [{tl['id']}] {tl['title']}")


def _resolve_tasklist(service, tasklist_ref: str) -> str:
    """Resolve a task list name or partial ID to a full ID."""
    if tasklist_ref == "@default":
        return "@default"
    result = service.tasklists().list(maxResults=100).execute()
    for tl in result.get("items", []):
        if tl["id"] == tasklist_ref or tl["title"].lower() == tasklist_ref.lower():
            return tl["id"]
        if tl["id"].startswith(tasklist_ref):
            return tl["id"]
    return tasklist_ref  # fallback: use as-is


# ─────────────────────────────────────────────
# Task CRUD
# ─────────────────────────────────────────────

@with_retry()
def list_tasks(tasklist: str = "@default", show_completed: bool = False, format_: str = "table"):
    """List tasks in a task list."""
    service = get_service()
    tasklist = _resolve_tasklist(service, tasklist)

    result = service.tasks().list(
        tasklist=tasklist,
        showCompleted=show_completed,
        showHidden=show_completed,
        maxResults=100,
    ).execute()
    tasks = result.get("items", [])

    if not tasks:
        print("No tasks found.")
        return

    if format_ == "json":
        output = []
        for t in tasks:
            output.append({
                "id": t["id"],
                "title": t.get("title", ""),
                "status": t.get("status", ""),
                "due": t.get("due", "")[:10] if t.get("due") else "",
                "notes": t.get("notes", ""),
                "updated": t.get("updated", "")[:10] if t.get("updated") else "",
            })
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    print(f"Tasks ({len(tasks)}):")
    for t in tasks:
        status_icon = "✅" if t.get("status") == "completed" else "☐"
        due = t.get("due", "")[:10] if t.get("due") else ""
        due_str = f"  [due: {due}]" if due else ""
        short_id = t["id"][:12]
        print(f"  {status_icon} [{short_id}] {t.get('title', '')}{due_str}")
        if t.get("notes"):
            for line in t["notes"].splitlines():
                print(f"      {line}")


@with_retry()
def show_task(task_id: str, tasklist: str = "@default"):
    """Show full details of a single task."""
    service = get_service()
    tasklist = _resolve_tasklist(service, tasklist)

    # Find full ID via list if partial
    full_id = _find_task_id(service, task_id, tasklist)
    if not full_id:
        print(f"Task not found: {task_id}", file=sys.stderr)
        sys.exit(1)

    task = service.tasks().get(tasklist=tasklist, task=full_id).execute()
    print(f"ID:      {task['id']}")
    print(f"Title:   {task.get('title', '')}")
    print(f"Status:  {task.get('status', '')}")
    if task.get("due"):
        print(f"Due:     {task['due'][:10]}")
    if task.get("notes"):
        print(f"Notes:   {task['notes']}")
    print(f"Updated: {task.get('updated', '')[:19]}")


@with_retry()
def create_task(
    title: str,
    tasklist: str = "@default",
    due: str = None,
    notes: str = None,
    parent: str = None,
):
    """Create a new Google Task."""
    service = get_service()
    tasklist = _resolve_tasklist(service, tasklist)

    body: dict = {"title": title, "status": "needsAction"}
    if due:
        # Normalize due date to RFC3339
        if "T" not in due:
            due = f"{due}T00:00:00.000Z"
        body["due"] = due
    if notes:
        body["notes"] = notes

    kwargs: dict = {"tasklist": tasklist, "body": body}
    if parent:
        kwargs["parent"] = parent

    result = service.tasks().insert(**kwargs).execute()
    print(f"✅ Task created: [{result['id'][:12]}] {title}")
    if due:
        print(f"   Due: {due[:10]}")


@with_retry()
def update_task(
    task_id: str,
    tasklist: str = "@default",
    title: str = None,
    due: str = None,
    notes: str = None,
):
    """Update an existing task."""
    service = get_service()
    tasklist = _resolve_tasklist(service, tasklist)
    full_id = _find_task_id(service, task_id, tasklist)
    if not full_id:
        print(f"Task not found: {task_id}", file=sys.stderr)
        sys.exit(1)

    # Fetch current
    task = service.tasks().get(tasklist=tasklist, task=full_id).execute()

    if title:
        task["title"] = title
    if due:
        if "T" not in due:
            due = f"{due}T00:00:00.000Z"
        task["due"] = due
    if notes is not None:
        task["notes"] = notes

    result = service.tasks().update(tasklist=tasklist, task=full_id, body=task).execute()
    print(f"✅ Task updated: [{result['id'][:12]}] {result.get('title', '')}")


@with_retry()
def complete_task(task_id: str, tasklist: str = "@default"):
    """Mark a task as completed."""
    service = get_service()
    tasklist = _resolve_tasklist(service, tasklist)
    full_id = _find_task_id(service, task_id, tasklist)
    if not full_id:
        print(f"Task not found: {task_id}", file=sys.stderr)
        sys.exit(1)

    service.tasks().patch(
        tasklist=tasklist,
        task=full_id,
        body={"status": "completed"},
    ).execute()
    print(f"✅ Task {task_id[:12]} marked as completed")


@with_retry()
def delete_task(task_id: str, tasklist: str = "@default"):
    """Delete a task."""
    service = get_service()
    tasklist = _resolve_tasklist(service, tasklist)
    full_id = _find_task_id(service, task_id, tasklist)
    if not full_id:
        print(f"Task not found: {task_id}", file=sys.stderr)
        sys.exit(1)

    service.tasks().delete(tasklist=tasklist, task=full_id).execute()
    print(f"🗑️  Task {task_id[:12]} deleted")


@with_retry()
def clear_completed(tasklist: str = "@default"):
    """Clear all completed tasks from a task list."""
    service = get_service()
    tasklist = _resolve_tasklist(service, tasklist)
    service.tasks().clear(tasklist=tasklist).execute()
    print("✅ Cleared all completed tasks")


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _find_task_id(service, task_id_or_partial: str, tasklist: str) -> str | None:
    """Find full task ID from a partial ID or exact match."""
    result = service.tasks().list(
        tasklist=tasklist, showCompleted=True, showHidden=True, maxResults=200
    ).execute()
    for t in result.get("items", []):
        if t["id"] == task_id_or_partial:
            return t["id"]
        if t["id"].startswith(task_id_or_partial):
            return t["id"]
    return None


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GARC Tasks Helper — Google Tasks operations")
    parser.add_argument("--tasklist", "-l", default="@default", help="Task list ID or name (default: @default)")
    parser.add_argument("--format", "-f", dest="format_", default="table", choices=["table", "json"])
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list-tasklists
    subparsers.add_parser("list-tasklists", help="Show all task lists")

    # list
    lp = subparsers.add_parser("list", help="List tasks")
    lp.add_argument("--completed", action="store_true", help="Include completed tasks")

    # show
    sp = subparsers.add_parser("show", help="Show a single task")
    sp.add_argument("--task-id", required=True)

    # create
    cp = subparsers.add_parser("create", help="Create a task")
    cp.add_argument("--title", required=True)
    cp.add_argument("--due", help="Due date (YYYY-MM-DD)")
    cp.add_argument("--notes", help="Task notes")
    cp.add_argument("--parent", help="Parent task ID (for subtasks)")

    # update
    up = subparsers.add_parser("update", help="Update a task")
    up.add_argument("--task-id", required=True)
    up.add_argument("--title")
    up.add_argument("--due")
    up.add_argument("--notes")

    # complete
    comp = subparsers.add_parser("complete", help="Mark task as completed")
    comp.add_argument("--task-id", required=True)

    # delete
    dp = subparsers.add_parser("delete", help="Delete a task")
    dp.add_argument("--task-id", required=True)

    # clear-completed
    subparsers.add_parser("clear-completed", help="Remove all completed tasks")

    args = parser.parse_args()

    try:
        if args.command == "list-tasklists":
            list_tasklists()
        elif args.command == "list":
            list_tasks(args.tasklist, args.completed, args.format_)
        elif args.command == "show":
            show_task(args.task_id, args.tasklist)
        elif args.command == "create":
            create_task(args.title, args.tasklist, args.due, args.notes, args.parent)
        elif args.command == "update":
            update_task(args.task_id, args.tasklist, args.title, args.due, args.notes)
        elif args.command == "complete":
            complete_task(args.task_id, args.tasklist)
        elif args.command == "delete":
            delete_task(args.task_id, args.tasklist)
        elif args.command == "clear-completed":
            clear_completed(args.tasklist)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
