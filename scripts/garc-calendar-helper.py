#!/usr/bin/env python3
"""
GARC Calendar Helper — Full Google Calendar operations
list / create / update / delete / search / freebusy / quick-add
"""

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from garc_core import build_service, utc_now, with_retry


def get_svc():
    return build_service("calendar", "v3")


def _parse_datetime(dt_str: str, tz: str = "Asia/Tokyo") -> dict:
    """Parse a datetime string into Google Calendar format."""
    if "T" in dt_str or ":" in dt_str:
        # Full datetime
        if "T" not in dt_str:
            dt_str = dt_str.replace(" ", "T")
        return {"dateTime": dt_str, "timeZone": tz}
    else:
        # Date only
        return {"date": dt_str}


def _format_event(event: dict) -> str:
    """Format an event for display."""
    summary = event.get("summary", "(no title)")
    start = event.get("start", {})
    end = event.get("end", {})
    start_str = start.get("dateTime", start.get("date", ""))[:16]
    end_str = end.get("dateTime", end.get("date", ""))[:16]
    location = event.get("location", "")
    attendees = event.get("attendees", [])
    attendee_str = f" ({len(attendees)} attendees)" if attendees else ""
    loc_str = f" @ {location[:30]}" if location else ""

    return f"[{event['id'][:10]}] {start_str} → {end_str}  {summary}{loc_str}{attendee_str}"


@with_retry()
def list_events(calendar_id: str = "primary", days_ahead: int = 7,
                days_back: int = 0, max_results: int = 50, query: str = ""):
    """List calendar events."""
    svc = get_svc()
    now = datetime.now(timezone.utc)
    time_min = (now - timedelta(days=days_back)).isoformat()
    time_max = (now + timedelta(days=days_ahead)).isoformat()

    kwargs = {
        "calendarId": calendar_id,
        "timeMin": time_min,
        "timeMax": time_max,
        "maxResults": max_results,
        "singleEvents": True,
        "orderBy": "startTime",
    }
    if query:
        kwargs["q"] = query

    result = svc.events().list(**kwargs).execute()
    events = result.get("items", [])

    if not events:
        print(f"No events found" + (f" for: {query}" if query else ""))
        return []

    label = f"next {days_ahead}d" if not days_back else f"±{days_ahead}d"
    print(f"Calendar events ({label}, {len(events)} results):")
    print()
    for event in events:
        print(f"  {_format_event(event)}")
    return events


@with_retry()
def create_event(summary: str, start: str, end: str,
                 description: str = "", location: str = "",
                 attendees: list = None, calendar_id: str = "primary",
                 send_notifications: bool = True, all_day: bool = False,
                 recurrence: str = "", timezone: str = "Asia/Tokyo"):
    """Create a calendar event."""
    svc = get_svc()

    start_obj = {"date": start} if all_day else _parse_datetime(start, timezone)
    end_obj = {"date": end} if all_day else _parse_datetime(end, timezone)

    body = {
        "summary": summary,
        "start": start_obj,
        "end": end_obj,
    }
    if description:
        body["description"] = description
    if location:
        body["location"] = location
    if attendees:
        body["attendees"] = [{"email": a} for a in attendees]
    if recurrence:
        body["recurrence"] = [recurrence]

    result = svc.events().insert(
        calendarId=calendar_id,
        body=body,
        sendNotifications=send_notifications
    ).execute()

    print(f"✅ Event created: {result['summary']}")
    print(f"   ID:    {result['id']}")
    print(f"   Start: {result['start'].get('dateTime', result['start'].get('date', ''))}")
    print(f"   End:   {result['end'].get('dateTime', result['end'].get('date', ''))}")
    print(f"   Link:  {result.get('htmlLink', '')}")
    return result


@with_retry()
def update_event(event_id: str, calendar_id: str = "primary", **updates):
    """Update a calendar event."""
    svc = get_svc()

    # Get existing event
    event = svc.events().get(calendarId=calendar_id, eventId=event_id).execute()

    if "summary" in updates:
        event["summary"] = updates["summary"]
    if "description" in updates:
        event["description"] = updates["description"]
    if "location" in updates:
        event["location"] = updates["location"]
    if "start" in updates:
        event["start"] = _parse_datetime(updates["start"])
    if "end" in updates:
        event["end"] = _parse_datetime(updates["end"])
    if "attendees_add" in updates:
        existing = {a["email"] for a in event.get("attendees", [])}
        for email in updates["attendees_add"]:
            if email not in existing:
                event.setdefault("attendees", []).append({"email": email})

    result = svc.events().update(
        calendarId=calendar_id, eventId=event_id, body=event
    ).execute()
    print(f"✅ Event updated: {result['summary']}")
    return result


@with_retry()
def delete_event(event_id: str, calendar_id: str = "primary"):
    """Delete a calendar event."""
    svc = get_svc()
    svc.events().delete(calendarId=calendar_id, eventId=event_id).execute()
    print(f"✅ Event deleted: {event_id}")


@with_retry()
def get_event(event_id: str, calendar_id: str = "primary"):
    """Get event details."""
    svc = get_svc()
    event = svc.events().get(calendarId=calendar_id, eventId=event_id).execute()

    print(f"Summary:     {event.get('summary', '')}")
    print(f"ID:          {event['id']}")
    start = event.get("start", {})
    end = event.get("end", {})
    print(f"Start:       {start.get('dateTime', start.get('date', ''))}")
    print(f"End:         {end.get('dateTime', end.get('date', ''))}")
    print(f"Location:    {event.get('location', '')}")
    print(f"Description: {event.get('description', '')}")
    attendees = event.get("attendees", [])
    if attendees:
        print(f"Attendees ({len(attendees)}):")
        for a in attendees:
            status = a.get("responseStatus", "unknown")
            status_icon = {"accepted": "✅", "declined": "❌", "tentative": "❓", "needsAction": "⏳"}.get(status, "")
            print(f"  {status_icon} {a.get('email', '')} ({a.get('displayName', '')})")
    print(f"Link:        {event.get('htmlLink', '')}")
    return event


@with_retry()
def freebusy(start: str, end: str, emails: list, timezone: str = "Asia/Tokyo"):
    """Check free/busy status for given email addresses."""
    svc = get_svc()

    body = {
        "timeMin": start if "T" in start else f"{start}T00:00:00Z",
        "timeMax": end if "T" in end else f"{end}T23:59:59Z",
        "timeZone": timezone,
        "items": [{"id": email} for email in emails]
    }

    result = svc.freebusy().query(body=body).execute()
    calendars = result.get("calendars", {})

    print(f"Free/Busy ({start} → {end}):")
    for email, data in calendars.items():
        busy = data.get("busy", [])
        if busy:
            print(f"\n  🔴 {email} — BUSY ({len(busy)} slots):")
            for slot in busy:
                print(f"     {slot['start'][:16]} → {slot['end'][:16]}")
        else:
            print(f"\n  ✅ {email} — FREE")

    return result


@with_retry()
def quick_add(text: str, calendar_id: str = "primary"):
    """Quick add an event from natural language text."""
    svc = get_svc()
    result = svc.events().quickAdd(calendarId=calendar_id, text=text).execute()
    print(f"✅ Quick add: {result.get('summary', '')}")
    print(f"   {result.get('start', {}).get('dateTime', '')[:16]}")
    return result


@with_retry()
def list_calendars():
    """List all accessible calendars."""
    svc = get_svc()
    result = svc.calendarList().list().execute()
    calendars = result.get("items", [])
    print(f"Calendars ({len(calendars)}):")
    for cal in calendars:
        primary = " (primary)" if cal.get("primary") else ""
        print(f"  [{cal['id'][:30]:<30}] {cal['summary']}{primary}")
    return calendars


def main():
    parser = argparse.ArgumentParser(description="GARC Calendar Helper")
    sub = parser.add_subparsers(dest="command")

    # list
    lp = sub.add_parser("list", help="List events")
    lp.add_argument("--calendar", default="primary")
    lp.add_argument("--days", type=int, default=7)
    lp.add_argument("--back", type=int, default=0, help="Days to look back")
    lp.add_argument("--max", type=int, default=50)
    lp.add_argument("--query", default="")

    # create
    cp = sub.add_parser("create", help="Create event")
    cp.add_argument("--summary", required=True)
    cp.add_argument("--start", required=True)
    cp.add_argument("--end", required=True)
    cp.add_argument("--description", default="")
    cp.add_argument("--location", default="")
    cp.add_argument("--attendees", nargs="+", default=[])
    cp.add_argument("--calendar", default="primary")
    cp.add_argument("--no-notify", action="store_true")
    cp.add_argument("--all-day", action="store_true")
    cp.add_argument("--recurrence", default="")
    cp.add_argument("--timezone", default="Asia/Tokyo")

    # update
    up = sub.add_parser("update", help="Update event")
    up.add_argument("event_id")
    up.add_argument("--summary")
    up.add_argument("--description")
    up.add_argument("--location")
    up.add_argument("--start")
    up.add_argument("--end")
    up.add_argument("--add-attendees", nargs="+", dest="attendees_add", default=[])
    up.add_argument("--calendar", default="primary")

    # delete
    dp = sub.add_parser("delete", help="Delete event")
    dp.add_argument("event_id")
    dp.add_argument("--calendar", default="primary")

    # get
    gp = sub.add_parser("get", help="Get event details")
    gp.add_argument("event_id")
    gp.add_argument("--calendar", default="primary")

    # freebusy
    fb = sub.add_parser("freebusy", help="Check free/busy")
    fb.add_argument("--start", required=True)
    fb.add_argument("--end", required=True)
    fb.add_argument("--emails", nargs="+", required=True)
    fb.add_argument("--timezone", default="Asia/Tokyo")

    # quick-add
    qa = sub.add_parser("quick-add", help="Quick add from natural language")
    qa.add_argument("text")
    qa.add_argument("--calendar", default="primary")

    # calendars
    sub.add_parser("calendars", help="List all calendars")

    args = parser.parse_args()

    if args.command == "list":
        list_events(args.calendar, args.days, args.back, args.max, args.query)
    elif args.command == "create":
        create_event(args.summary, args.start, args.end, args.description,
                     args.location, args.attendees, args.calendar,
                     not args.no_notify, args.all_day, args.recurrence, args.timezone)
    elif args.command == "update":
        updates = {}
        for k in ["summary", "description", "location", "start", "end"]:
            v = getattr(args, k, None)
            if v:
                updates[k] = v
        if args.attendees_add:
            updates["attendees_add"] = args.attendees_add
        update_event(args.event_id, args.calendar, **updates)
    elif args.command == "delete":
        delete_event(args.event_id, args.calendar)
    elif args.command == "get":
        get_event(args.event_id, args.calendar)
    elif args.command == "freebusy":
        freebusy(args.start, args.end, args.emails, args.timezone)
    elif args.command == "quick-add":
        quick_add(args.text, args.calendar)
    elif args.command == "calendars":
        list_calendars()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
