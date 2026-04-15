#!/usr/bin/env python3
"""
GARC Auth Helper — OAuth scope inference and token management
Mirrors LARC's scope inference engine but for Google Workspace OAuth scopes
"""

import argparse
import json
import os
import sys
from pathlib import Path

GARC_DIR = Path(__file__).parent.parent
SCOPE_MAP_PATH = GARC_DIR / "config" / "scope-map.json"
GARC_CONFIG_DIR = Path.home() / ".garc"
TOKEN_FILE = Path(os.environ.get("GARC_TOKEN_FILE", str(GARC_CONFIG_DIR / "token.json")))
CREDENTIALS_FILE = Path(os.environ.get("GARC_CREDENTIALS_FILE", str(GARC_CONFIG_DIR / "credentials.json")))


def load_scope_map():
    with open(SCOPE_MAP_PATH) as f:
        return json.load(f)


def suggest_scopes(task_description: str):
    """Infer minimum OAuth scopes for a natural-language task description."""
    scope_map = load_scope_map()
    task_description_lower = task_description.lower()

    matched_tasks = []
    matched_scopes = set()

    # Keyword pattern matching
    for task_type, patterns in scope_map.get("keyword_patterns", {}).items():
        for pattern in patterns:
            if pattern.lower() in task_description_lower:
                if task_type not in matched_tasks:
                    matched_tasks.append(task_type)
                task_def = scope_map["tasks"].get(task_type, {})
                for scope in task_def.get("scopes", []):
                    matched_scopes.add(scope)

    if not matched_tasks:
        print("No specific task types matched. General writer profile recommended.")
        print("\nSuggested profile: writer")
        profile = scope_map["profiles"]["writer"]
        print(f"Description: {profile['description']}")
        print("\nScopes:")
        for scope in profile["scopes"]:
            print(f"  - {scope}")
        return

    print(f"Task analysis: \"{task_description}\"")
    print(f"\nMatched task types: {', '.join(matched_tasks)}")

    # Show gate policies
    print("\nExecution gates:")
    for task_type in matched_tasks:
        task_def = scope_map["tasks"].get(task_type, {})
        gate = task_def.get("gate", "none")
        desc = task_def.get("description", "")
        gate_icon = {"none": "✅", "preview": "⚠️", "approval": "🔒"}.get(gate, "❓")
        print(f"  {gate_icon} {task_type} ({gate}): {desc}")

    print("\nRequired OAuth scopes:")
    for scope in sorted(matched_scopes):
        print(f"  - {scope}")

    # Identity type
    identities = set()
    for task_type in matched_tasks:
        task_def = scope_map["tasks"].get(task_type, {})
        identities.add(task_def.get("identity", "user_access_token"))

    print(f"\nIdentity type: {', '.join(identities)}")

    # Highest gate level
    gate_order = {"none": 0, "preview": 1, "approval": 2}
    max_gate = max(
        (scope_map["tasks"].get(t, {}).get("gate", "none") for t in matched_tasks),
        key=lambda g: gate_order.get(g, 0),
        default="none"
    )
    gate_messages = {
        "none": "✅ All operations are read-only. Can execute immediately.",
        "preview": "⚠️  Some operations have external visibility. Use --confirm flag.",
        "approval": "🔒 High-risk operations detected. Human approval required before execution."
    }
    print(f"\nGate requirement: {gate_messages.get(max_gate, '')}")

    # Recommend profile
    print("\nRecommended garc auth login command:")
    if max_gate == "none":
        print("  garc auth login --profile readonly")
    elif max_gate == "preview":
        print("  garc auth login --profile writer")
    else:
        print("  garc auth login --profile backoffice_agent")


def check_scopes(profile: str):
    """Check if current token has the required scopes for a profile."""
    scope_map = load_scope_map()

    if profile not in scope_map.get("profiles", {}):
        print(f"Unknown profile: {profile}")
        print(f"Available profiles: {', '.join(scope_map['profiles'].keys())}")
        sys.exit(1)

    required_scopes = set(scope_map["profiles"][profile]["scopes"])

    if not TOKEN_FILE.exists():
        print(f"No token file found at {TOKEN_FILE}")
        print(f"Run: garc auth login --profile {profile}")
        sys.exit(1)

    try:
        with open(TOKEN_FILE) as f:
            token_data = json.load(f)
        current_scopes = set(token_data.get("scopes", "").split() if isinstance(token_data.get("scopes"), str)
                              else token_data.get("scopes", []))
    except (json.JSONDecodeError, KeyError):
        print(f"Could not read token file: {TOKEN_FILE}")
        sys.exit(1)

    missing = required_scopes - current_scopes

    if not missing:
        print(f"✅ Current token satisfies '{profile}' profile requirements.")
        print(f"   Required: {len(required_scopes)} scopes — all present.")
    else:
        print(f"❌ Missing scopes for '{profile}' profile:")
        for scope in sorted(missing):
            print(f"  - {scope}")
        print(f"\nRun: garc auth login --profile {profile}")


def login(profile: str):
    """Launch OAuth2 authorization flow for the given profile."""
    scope_map = load_scope_map()

    if profile not in scope_map.get("profiles", {}):
        print(f"Unknown profile: {profile}")
        sys.exit(1)

    scopes = scope_map["profiles"][profile]["scopes"]
    description = scope_map["profiles"][profile]["description"]

    print(f"OAuth2 authorization for profile: {profile}")
    print(f"Description: {description}")
    print(f"\nRequested scopes ({len(scopes)}):")
    for scope in scopes:
        print(f"  - {scope}")

    if not CREDENTIALS_FILE.exists():
        print(f"\nError: credentials.json not found at {CREDENTIALS_FILE}")
        print("Download it from Google Cloud Console → APIs & Services → Credentials")
        print("OAuth 2.0 Client IDs → Download JSON → save as ~/.garc/credentials.json")
        sys.exit(1)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        import google.oauth2.credentials

        # Check if we have valid existing credentials
        creds = None
        if TOKEN_FILE.exists():
            creds = google.oauth2.credentials.Credentials.from_authorized_user_file(str(TOKEN_FILE))

        if creds and creds.valid:
            print(f"\n✅ Already authenticated. Token file: {TOKEN_FILE}")
            return

        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token...")
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), scopes)
            creds = flow.run_local_server(port=0)

        GARC_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print(f"\n✅ Token saved to {TOKEN_FILE}")

    except ImportError:
        print("\nNote: google-auth-oauthlib not installed.")
        print("Install with: pip install google-auth-oauthlib google-api-python-client")
        print("\nManual authorization URL would use scopes:")
        for scope in scopes:
            print(f"  {scope}")


def show_status():
    """Show current token information."""
    if not TOKEN_FILE.exists():
        print(f"No token file found at {TOKEN_FILE}")
        print("Run: garc auth login --profile writer")
        return

    try:
        with open(TOKEN_FILE) as f:
            token_data = json.load(f)
        print(f"Token file: {TOKEN_FILE}")
        print(f"Client ID: {token_data.get('client_id', 'N/A')[:20]}...")

        scopes = token_data.get("scopes", [])
        if isinstance(scopes, str):
            scopes = scopes.split()
        print(f"\nGranted scopes ({len(scopes)}):")
        for scope in sorted(scopes):
            short = scope.replace("https://www.googleapis.com/auth/", "")
            print(f"  - {short}")

        expiry = token_data.get("expiry", "unknown")
        print(f"\nExpiry: {expiry}")

    except Exception as e:
        print(f"Error reading token: {e}")


def revoke_token():
    """Revoke the stored OAuth token and delete the token file."""
    if not TOKEN_FILE.exists():
        print(f"No token file found at {TOKEN_FILE}")
        return

    try:
        import requests as req_lib
        with open(TOKEN_FILE) as f:
            token_data = json.load(f)

        token = token_data.get("token") or token_data.get("access_token", "")
        if token:
            resp = req_lib.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )
            if resp.status_code == 200:
                print("✅ Token revoked at Google.")
            else:
                print(f"⚠️  Revocation response: {resp.status_code} — {resp.text[:80]}")
        else:
            print("⚠️  No access token in token file — skipping remote revocation.")
    except Exception as e:
        print(f"⚠️  Could not revoke token remotely: {e}")

    TOKEN_FILE.unlink(missing_ok=True)
    print(f"✅ Deleted: {TOKEN_FILE}")
    print("   Run 'garc auth login' to re-authenticate.")


def service_account_verify(sa_file: str):
    """Verify service account credentials by listing Drive files."""
    sa_path = Path(sa_file)
    if not sa_path.exists():
        print(f"❌ Service account file not found: {sa_path}")
        sys.exit(1)

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        with open(sa_path) as f:
            sa_data = json.load(f)

        print(f"Service Account: {sa_data.get('client_email', 'N/A')}")
        print(f"Project:         {sa_data.get('project_id', 'N/A')}")

        scopes = ["https://www.googleapis.com/auth/drive.readonly"]
        creds = service_account.Credentials.from_service_account_file(str(sa_path), scopes=scopes)

        # Check if GARC_IMPERSONATE_EMAIL is set for DWD
        impersonate = os.environ.get("GARC_IMPERSONATE_EMAIL", "")
        if impersonate:
            creds = creds.with_subject(impersonate)
            print(f"Impersonating:   {impersonate}")

        svc = build("drive", "v3", credentials=creds, cache_discovery=False)
        resp = svc.files().list(pageSize=1, fields="files(id,name)").execute()
        files = resp.get("files", [])
        print(f"\n✅ Service account is valid. Drive access confirmed ({len(files)} file(s) visible).")

        if not impersonate:
            print("\n💡 Tip: For Domain-wide Delegation, set GARC_IMPERSONATE_EMAIL=user@yourdomain.com")
            print("   Then re-run 'garc auth service-account verify'.")

    except Exception as e:
        print(f"❌ Service account verification failed: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="GARC Auth Helper")
    subparsers = parser.add_subparsers(dest="command")

    # suggest
    suggest_parser = subparsers.add_parser("suggest", help="Suggest scopes for a task")
    suggest_parser.add_argument("task", nargs="+", help="Task description")

    # check
    check_parser = subparsers.add_parser("check", help="Check current token scopes")
    check_parser.add_argument("--profile", default="writer", help="Profile to check against")

    # login
    login_parser = subparsers.add_parser("login", help="Launch OAuth2 flow")
    login_parser.add_argument("--profile", default="writer", help="Profile to authorize")

    # status
    subparsers.add_parser("status", help="Show token status")

    # revoke
    subparsers.add_parser("revoke", help="Revoke and delete stored token")

    # service-account-verify
    sav_parser = subparsers.add_parser("service-account-verify", help="Verify service account credentials")
    sav_parser.add_argument("--file", required=True, help="Path to service account JSON file")

    args = parser.parse_args()

    if args.command == "suggest":
        suggest_scopes(" ".join(args.task))
    elif args.command == "check":
        check_scopes(args.profile)
    elif args.command == "login":
        login(args.profile)
    elif args.command == "status":
        show_status()
    elif args.command == "revoke":
        revoke_token()
    elif args.command == "service-account-verify":
        service_account_verify(args.file)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
