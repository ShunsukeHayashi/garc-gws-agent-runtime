#!/usr/bin/env python3
"""
GARC People Helper — Google People API (Contacts & Directory)
search / list / show / create / update / delete
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from garc_core import build_service, with_retry

PERSON_FIELDS = "names,emailAddresses,phoneNumbers,organizations,addresses,biographies"
CONTACT_SCOPES = [
    "https://www.googleapis.com/auth/contacts",
    "https://www.googleapis.com/auth/directory.readonly",
]


def get_service():
    return build_service("people", "v1", scopes=CONTACT_SCOPES)


def _fmt_person(p: dict, short: bool = False) -> str:
    """Format a person resource as a readable string."""
    name = p.get("names", [{}])[0].get("displayName", "(no name)")
    emails = [e.get("value", "") for e in p.get("emailAddresses", [])]
    phones = [ph.get("value", "") for ph in p.get("phoneNumbers", [])]
    orgs = [o.get("name", "") for o in p.get("organizations", [])]
    resource = p.get("resourceName", "")
    short_id = resource.split("/")[-1] if "/" in resource else resource

    if short:
        email_str = emails[0] if emails else ""
        org_str = f" ({orgs[0]})" if orgs else ""
        return f"[{short_id[:10]}] {name}{org_str} — {email_str}"

    lines = [f"Name:     {name}", f"ID:       {short_id}"]
    for e in emails:
        lines.append(f"Email:    {e}")
    for ph in phones:
        lines.append(f"Phone:    {ph}")
    for o in p.get("organizations", []):
        org_parts = [x for x in [o.get("name"), o.get("title"), o.get("department")] if x]
        lines.append(f"Org:      {' / '.join(org_parts)}")
    for bio in p.get("biographies", []):
        lines.append(f"Bio:      {bio.get('value', '')[:80]}")
    return "\n".join(lines)


# ─────────────────────────────────────────────
# Search (Directory + personal contacts)
# ─────────────────────────────────────────────

@with_retry()
def search_contacts(query: str, max_results: int = 20, format_: str = "table"):
    """Search contacts from the user's personal contacts."""
    service = get_service()
    result = service.people().searchContacts(
        query=query,
        readMask=PERSON_FIELDS,
        pageSize=min(max_results, 30),
    ).execute()

    results = result.get("results", [])
    if not results:
        print(f"No contacts found for: {query}")
        return

    if format_ == "json":
        print(json.dumps([r.get("person", {}) for r in results], ensure_ascii=False, indent=2))
        return

    print(f"Contacts matching '{query}' ({len(results)}):")
    for r in results:
        print(f"  {_fmt_person(r.get('person', {}), short=True)}")


@with_retry()
def search_directory(query: str, max_results: int = 20, format_: str = "table"):
    """Search the Google Workspace directory (org-wide)."""
    service = get_service()
    try:
        result = service.people().searchDirectoryPeople(
            query=query,
            readMask=PERSON_FIELDS,
            sources=["DIRECTORY_SOURCE_TYPE_DOMAIN_PROFILE", "DIRECTORY_SOURCE_TYPE_DOMAIN_CONTACT"],
            pageSize=min(max_results, 30),
        ).execute()
    except Exception as e:
        if "403" in str(e):
            print("Directory search requires Google Workspace (not personal Gmail).", file=sys.stderr)
        else:
            raise
        return

    people = result.get("people", [])
    if not people:
        print(f"No directory results for: {query}")
        return

    if format_ == "json":
        print(json.dumps(people, ensure_ascii=False, indent=2))
        return

    print(f"Directory results for '{query}' ({len(people)}):")
    for p in people:
        print(f"  {_fmt_person(p, short=True)}")


# ─────────────────────────────────────────────
# Contacts CRUD
# ─────────────────────────────────────────────

@with_retry()
def list_contacts(max_results: int = 50, format_: str = "table"):
    """List all personal contacts."""
    service = get_service()
    result = service.people().connections().list(
        resourceName="people/me",
        personFields=PERSON_FIELDS,
        pageSize=min(max_results, 1000),
        sortOrder="LAST_MODIFIED_DESCENDING",
    ).execute()

    people = result.get("connections", [])
    if not people:
        print("No contacts found.")
        return

    if format_ == "json":
        print(json.dumps(people, ensure_ascii=False, indent=2))
        return

    print(f"Contacts ({len(people)}):")
    for p in people:
        print(f"  {_fmt_person(p, short=True)}")


@with_retry()
def show_contact(contact_id: str):
    """Show full details of a contact."""
    service = get_service()
    # Accept short ID or full resource name
    if not contact_id.startswith("people/"):
        contact_id = f"people/{contact_id}"
    person = service.people().get(
        resourceName=contact_id,
        personFields=PERSON_FIELDS,
    ).execute()
    print(_fmt_person(person))


@with_retry()
def create_contact(
    name: str,
    email: str = None,
    phone: str = None,
    company: str = None,
    title: str = None,
    notes: str = None,
):
    """Create a new contact."""
    service = get_service()
    body: dict = {}

    # Name
    parts = name.split(" ", 1)
    body["names"] = [{
        "givenName": parts[0],
        "familyName": parts[1] if len(parts) > 1 else "",
    }]
    if email:
        body["emailAddresses"] = [{"value": email, "type": "work"}]
    if phone:
        body["phoneNumbers"] = [{"value": phone, "type": "work"}]
    if company or title:
        body["organizations"] = [{
            "name": company or "",
            "title": title or "",
            "type": "work",
        }]
    if notes:
        body["biographies"] = [{"value": notes, "contentType": "TEXT_PLAIN"}]

    result = service.people().createContact(body=body).execute()
    resource_id = result.get("resourceName", "").split("/")[-1]
    print(f"✅ Contact created: [{resource_id}] {name}")
    if email:
        print(f"   Email: {email}")


@with_retry()
def update_contact(
    contact_id: str,
    name: str = None,
    email: str = None,
    phone: str = None,
    company: str = None,
    title: str = None,
):
    """Update fields of an existing contact."""
    service = get_service()
    if not contact_id.startswith("people/"):
        contact_id = f"people/{contact_id}"

    # Fetch current
    person = service.people().get(
        resourceName=contact_id,
        personFields=PERSON_FIELDS,
    ).execute()
    etag = person.get("etag")
    update_fields = []

    if name:
        parts = name.split(" ", 1)
        person["names"] = [{
            "givenName": parts[0],
            "familyName": parts[1] if len(parts) > 1 else "",
        }]
        update_fields.append("names")

    if email:
        person["emailAddresses"] = [{"value": email, "type": "work"}]
        update_fields.append("emailAddresses")

    if phone:
        person["phoneNumbers"] = [{"value": phone, "type": "work"}]
        update_fields.append("phoneNumbers")

    if company or title:
        existing_org = (person.get("organizations") or [{}])[0]
        person["organizations"] = [{
            "name": company or existing_org.get("name", ""),
            "title": title or existing_org.get("title", ""),
            "type": "work",
        }]
        update_fields.append("organizations")

    if not update_fields:
        print("No updates specified.")
        return

    person["etag"] = etag
    service.people().updateContact(
        resourceName=contact_id,
        updatePersonFields=",".join(update_fields),
        body=person,
    ).execute()
    short_id = contact_id.split("/")[-1]
    print(f"✅ Contact updated: [{short_id}]")


@with_retry()
def delete_contact(contact_id: str):
    """Delete a contact."""
    service = get_service()
    if not contact_id.startswith("people/"):
        contact_id = f"people/{contact_id}"
    service.people().deleteContact(resourceName=contact_id).execute()
    short_id = contact_id.split("/")[-1]
    print(f"🗑️  Contact deleted: [{short_id}]")


# ─────────────────────────────────────────────
# Email Lookup helper (used by gmail.sh)
# ─────────────────────────────────────────────

@with_retry()
def lookup_email(name_or_email: str):
    """Quick lookup: find email for a name. Tries contacts then directory."""
    service = get_service()

    # Try personal contacts first
    try:
        result = service.people().searchContacts(
            query=name_or_email,
            readMask="names,emailAddresses",
            pageSize=5,
        ).execute()
        for r in result.get("results", []):
            p = r.get("person", {})
            emails = p.get("emailAddresses", [])
            if emails:
                name = p.get("names", [{}])[0].get("displayName", "")
                email = emails[0].get("value", "")
                print(f"{name} <{email}>")
                return
    except Exception:
        pass

    # Try directory
    try:
        result = service.people().searchDirectoryPeople(
            query=name_or_email,
            readMask="names,emailAddresses",
            sources=["DIRECTORY_SOURCE_TYPE_DOMAIN_PROFILE"],
            pageSize=5,
        ).execute()
        for p in result.get("people", []):
            emails = p.get("emailAddresses", [])
            if emails:
                name = p.get("names", [{}])[0].get("displayName", "")
                email = emails[0].get("value", "")
                print(f"{name} <{email}>")
                return
    except Exception:
        pass

    print(f"Not found: {name_or_email}")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GARC People Helper — Google Contacts & Directory")
    parser.add_argument("--format", "-f", dest="format_", default="table", choices=["table", "json"])
    subparsers = parser.add_subparsers(dest="command", required=True)

    # search
    sp = subparsers.add_parser("search", help="Search personal contacts")
    sp.add_argument("query", nargs="+")
    sp.add_argument("--max", type=int, default=20)

    # directory
    dp = subparsers.add_parser("directory", help="Search GWS directory (org-wide)")
    dp.add_argument("query", nargs="+")
    dp.add_argument("--max", type=int, default=20)

    # list
    lp = subparsers.add_parser("list", help="List all personal contacts")
    lp.add_argument("--max", type=int, default=50)

    # show
    shp = subparsers.add_parser("show", help="Show a contact by ID")
    shp.add_argument("contact_id")

    # create
    cp = subparsers.add_parser("create", help="Create a new contact")
    cp.add_argument("--name", required=True)
    cp.add_argument("--email")
    cp.add_argument("--phone")
    cp.add_argument("--company")
    cp.add_argument("--title")
    cp.add_argument("--notes")

    # update
    up = subparsers.add_parser("update", help="Update a contact")
    up.add_argument("contact_id")
    up.add_argument("--name")
    up.add_argument("--email")
    up.add_argument("--phone")
    up.add_argument("--company")
    up.add_argument("--title")

    # delete
    delp = subparsers.add_parser("delete", help="Delete a contact")
    delp.add_argument("contact_id")

    # lookup
    look = subparsers.add_parser("lookup", help="Quick email lookup by name")
    look.add_argument("query", nargs="+")

    args = parser.parse_args()

    try:
        if args.command == "search":
            search_contacts(" ".join(args.query), args.max, args.format_)
        elif args.command == "directory":
            search_directory(" ".join(args.query), args.max, args.format_)
        elif args.command == "list":
            list_contacts(args.max, args.format_)
        elif args.command == "show":
            show_contact(args.contact_id)
        elif args.command == "create":
            create_contact(args.name, args.email, args.phone, args.company, args.title, args.notes)
        elif args.command == "update":
            update_contact(args.contact_id, args.name, args.email, args.phone, args.company, args.title)
        elif args.command == "delete":
            delete_contact(args.contact_id)
        elif args.command == "lookup":
            lookup_email(" ".join(args.query))
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
