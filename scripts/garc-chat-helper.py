#!/usr/bin/env python3
"""
GARC Chat Helper — Google Chat Space message operations
send / list-spaces / list-messages
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from garc_core import build_service


def get_svc():
    """Build Google Chat service."""
    return build_service("chat", "v1")


def send_message(space_id: str, message: str, thread_key: str = "") -> dict:
    """Send a plain-text message to a Chat space."""
    svc = get_svc()

    body: dict = {"text": message}
    params: dict = {"parent": space_id}

    if thread_key:
        body["thread"] = {"threadKey": thread_key}
        params["messageReplyOption"] = "REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"

    result = svc.spaces().messages().create(**params, body=body).execute()
    msg_name = result.get("name", "")
    print(f"✅ Message sent: {msg_name}")
    return result


def list_spaces() -> list:
    """List all Chat spaces the bot has access to."""
    svc = get_svc()
    result = svc.spaces().list().execute()
    spaces = result.get("spaces", [])
    if not spaces:
        print("No spaces found.")
        return []
    print(f"Spaces ({len(spaces)}):")
    for s in spaces:
        display = s.get("displayName", "(no name)")
        name = s.get("name", "")
        stype = s.get("spaceType", "")
        print(f"  {name:<35}  {display:<30}  {stype}")
    return spaces


def list_messages(space_id: str, max_results: int = 25) -> list:
    """List recent messages in a Chat space."""
    svc = get_svc()
    result = svc.spaces().messages().list(
        parent=space_id,
        pageSize=max_results,
    ).execute()
    messages = result.get("messages", [])
    if not messages:
        print(f"No messages in {space_id}")
        return []
    print(f"Messages ({len(messages)}):")
    for m in messages:
        sender = (m.get("sender") or {}).get("displayName", "?")
        text = m.get("text", "")[:80]
        create_time = m.get("createTime", "")[:19]
        print(f"  [{create_time}] {sender}: {text}")
    return messages


def main():
    parser = argparse.ArgumentParser(description="GARC Chat Helper")
    sub = parser.add_subparsers(dest="command")

    sp = sub.add_parser("send", help="Send a message to a Chat space")
    sp.add_argument("--space-id", required=True, help="Chat space ID (e.g. spaces/AAABBB)")
    sp.add_argument("--message", required=True, help="Message text")
    sp.add_argument("--thread-key", default="", help="Thread key for threaded replies")

    sub.add_parser("list-spaces", help="List accessible Chat spaces")

    lmp = sub.add_parser("list-messages", help="List messages in a space")
    lmp.add_argument("--space-id", required=True)
    lmp.add_argument("--max", type=int, default=25)

    args = parser.parse_args()

    if args.command == "send":
        send_message(args.space_id, args.message, args.thread_key)
    elif args.command == "list-spaces":
        list_spaces()
    elif args.command == "list-messages":
        list_messages(args.space_id, args.max)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
