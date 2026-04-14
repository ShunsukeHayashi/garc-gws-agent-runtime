#!/usr/bin/env python3
"""
GARC Gmail Helper — Full Gmail operations
send / search / read / list / draft / thread / label / reply / forward
"""

import argparse
import base64
import json
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from garc_core import build_service, utc_now, with_retry


def get_svc():
    return build_service("gmail", "v1")


@with_retry()
def send_email(to: str, subject: str, body: str, cc: str = "",
               bcc: str = "", html: bool = False, reply_to: str = ""):
    """Send an email via Gmail."""
    svc = get_svc()

    if html:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(body, "html"))
    else:
        msg = MIMEText(body, "plain")

    msg["to"] = to
    msg["subject"] = subject
    if cc:
        msg["cc"] = cc
    if bcc:
        msg["bcc"] = bcc
    if reply_to:
        msg["reply-to"] = reply_to

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    result = svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    print(f"✅ Email sent")
    print(f"   To:      {to}")
    print(f"   Subject: {subject}")
    print(f"   ID:      {result['id']}")
    return result


@with_retry()
def reply_to_thread(thread_id: str, message_id: str, to: str, subject: str, body: str):
    """Reply to an existing Gmail thread."""
    svc = get_svc()

    msg = MIMEText(body, "plain")
    msg["to"] = to
    msg["subject"] = subject if subject.startswith("Re:") else f"Re: {subject}"
    msg["in-reply-to"] = message_id
    msg["references"] = message_id

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    result = svc.users().messages().send(userId="me", body={
        "raw": raw, "threadId": thread_id
    }).execute()
    print(f"✅ Reply sent (thread: {thread_id[:12]})")
    return result


@with_retry()
def search_emails(query: str, max_results: int = 20, include_body: bool = False):
    """Search Gmail messages."""
    svc = get_svc()

    result = svc.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()
    messages = result.get("messages", [])

    if not messages:
        print(f"No results for: {query}")
        return []

    print(f"Found {len(messages)} messages for: {query}")
    print()

    detailed = []
    for m in messages:
        msg = svc.users().messages().get(
            userId="me", id=m["id"],
            format="full" if include_body else "metadata",
            metadataHeaders=["From", "To", "Subject", "Date"]
        ).execute()

        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        entry = {
            "id": msg["id"],
            "thread_id": msg["threadId"],
            "subject": headers.get("Subject", "(no subject)"),
            "from": headers.get("From", ""),
            "to": headers.get("To", ""),
            "date": headers.get("Date", ""),
            "labels": msg.get("labelIds", []),
            "snippet": msg.get("snippet", ""),
        }

        if include_body:
            entry["body"] = _extract_body(msg.get("payload", {}))

        detailed.append(entry)
        print(f"  [{entry['id'][:10]}] {entry['subject'][:50]}")
        print(f"    From: {entry['from'][:50]}  Date: {entry['date'][:24]}")
        if entry["snippet"]:
            print(f"    {entry['snippet'][:100]}...")
        print()

    return detailed


@with_retry()
def read_email(message_id: str):
    """Read a specific email message."""
    svc = get_svc()

    msg = svc.users().messages().get(
        userId="me", id=message_id, format="full"
    ).execute()

    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
    body = _extract_body(msg.get("payload", {}))

    print(f"Subject: {headers.get('Subject', '(no subject)')}")
    print(f"From:    {headers.get('From', '')}")
    print(f"To:      {headers.get('To', '')}")
    print(f"Date:    {headers.get('Date', '')}")
    print(f"Labels:  {', '.join(msg.get('labelIds', []))}")
    print()
    print("─" * 60)
    print(body)

    return {"headers": headers, "body": body, "id": message_id}


@with_retry()
def list_inbox(max_results: int = 20, label: str = "INBOX", unread_only: bool = False, format_: str = "table"):
    """List inbox messages."""
    import json as _json
    svc = get_svc()
    q = "is:unread" if unread_only else f"label:{label}"
    result = svc.users().messages().list(userId="me", q=q, maxResults=max_results).execute()
    message_ids = [m["id"] for m in result.get("messages", [])]

    messages = []
    for msg_id in message_ids:
        msg = svc.users().messages().get(userId="me", id=msg_id, format="metadata",
                                          metadataHeaders=["From", "Subject", "Date"]).execute()
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        messages.append({
            "id":      msg["id"],
            "from":    headers.get("From", ""),
            "subject": headers.get("Subject", "(no subject)"),
            "date":    headers.get("Date", ""),
            "snippet": msg.get("snippet", "")[:100],
        })

    if format_ == "json":
        print(_json.dumps(messages, ensure_ascii=False, indent=2))
        return messages

    print(f"Inbox {'(unread) ' if unread_only else ''}({len(messages)}):")
    for m in messages:
        sender = m["from"][:30]
        subj   = m["subject"][:45]
        print(f"  [{m['id'][:12]}] {sender:<30} {subj}")
    return messages


@with_retry()
def create_draft(to: str, subject: str, body: str, cc: str = ""):
    """Create a Gmail draft."""
    svc = get_svc()

    msg = MIMEText(body, "plain")
    msg["to"] = to
    msg["subject"] = subject
    if cc:
        msg["cc"] = cc

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    result = svc.users().drafts().create(
        userId="me", body={"message": {"raw": raw}}
    ).execute()
    print(f"✅ Draft created: {result['id']}")
    return result


@with_retry()
def list_labels():
    """List all Gmail labels."""
    svc = get_svc()
    result = svc.users().labels().list(userId="me").execute()
    labels = result.get("labels", [])
    print(f"Gmail labels ({len(labels)}):")
    for label in sorted(labels, key=lambda x: x["name"]):
        print(f"  [{label['id'][:15]:<15}] {label['name']}")


@with_retry()
def get_profile():
    """Get Gmail account profile."""
    svc = get_svc()
    profile = svc.users().getProfile(userId="me").execute()
    print(f"Gmail: {profile['emailAddress']}")
    print(f"Messages: {profile.get('messagesTotal', 'N/A'):,}")
    print(f"Threads:  {profile.get('threadsTotal', 'N/A'):,}")
    return profile


def _extract_body(payload: dict, prefer_plain: bool = True) -> str:
    """Recursively extract email body text."""
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")

    if body_data:
        text = base64.urlsafe_b64decode(body_data + "==").decode("utf-8", errors="replace")
        if prefer_plain and mime_type == "text/plain":
            return text
        if not prefer_plain and mime_type == "text/html":
            return text
        if mime_type in ("text/plain", "text/html"):
            return text

    for part in payload.get("parts", []):
        result = _extract_body(part, prefer_plain)
        if result:
            return result
    return ""


def main():
    parser = argparse.ArgumentParser(description="GARC Gmail Helper")
    sub = parser.add_subparsers(dest="command")

    # send
    sp = sub.add_parser("send", help="Send email")
    sp.add_argument("--to", required=True)
    sp.add_argument("--subject", required=True)
    sp.add_argument("--body", required=True)
    sp.add_argument("--cc", default="")
    sp.add_argument("--bcc", default="")
    sp.add_argument("--html", action="store_true")
    sp.add_argument("--reply-to", default="")

    # reply
    rp = sub.add_parser("reply", help="Reply to thread")
    rp.add_argument("--thread-id", required=True)
    rp.add_argument("--message-id", required=True)
    rp.add_argument("--to", required=True)
    rp.add_argument("--subject", required=True)
    rp.add_argument("--body", required=True)

    # search
    sp2 = sub.add_parser("search", help="Search emails")
    sp2.add_argument("query")
    sp2.add_argument("--max", type=int, default=20)
    sp2.add_argument("--body", action="store_true", help="Include body")

    # read
    rp2 = sub.add_parser("read", help="Read email")
    rp2.add_argument("message_id")

    # inbox
    ip = sub.add_parser("inbox", help="List inbox")
    ip.add_argument("--max", type=int, default=20)
    ip.add_argument("--unread", action="store_true")
    ip.add_argument("--format", dest="format_", default="table", choices=["table", "json"])

    # draft
    dp = sub.add_parser("draft", help="Create draft")
    dp.add_argument("--to", required=True)
    dp.add_argument("--subject", required=True)
    dp.add_argument("--body", required=True)
    dp.add_argument("--cc", default="")

    # labels
    sub.add_parser("labels", help="List labels")

    # profile
    sub.add_parser("profile", help="Show account profile")

    args = parser.parse_args()

    if args.command == "send":
        send_email(args.to, args.subject, args.body, args.cc, args.bcc, args.html, args.reply_to)
    elif args.command == "reply":
        reply_to_thread(args.thread_id, args.message_id, args.to, args.subject, args.body)
    elif args.command == "search":
        search_emails(args.query, args.max, args.body)
    elif args.command == "read":
        read_email(args.message_id)
    elif args.command == "inbox":
        list_inbox(args.max, unread_only=args.unread, format_=args.format_)
    elif args.command == "draft":
        create_draft(args.to, args.subject, args.body, args.cc)
    elif args.command == "labels":
        list_labels()
    elif args.command == "profile":
        get_profile()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
