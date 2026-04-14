#!/usr/bin/env python3
"""
GARC Core — Shared utilities: auth, service builders, retry, output formatting
"""

import json
import os
import sys
import time
import functools
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

GARC_CONFIG_DIR = Path(os.environ.get("GARC_CONFIG_DIR", Path.home() / ".garc"))
TOKEN_FILE = Path(os.environ.get("GARC_TOKEN_FILE", GARC_CONFIG_DIR / "token.json"))
CREDENTIALS_FILE = Path(os.environ.get("GARC_CREDENTIALS_FILE", GARC_CONFIG_DIR / "credentials.json"))
SERVICE_ACCOUNT_FILE = Path(os.environ.get("GARC_SERVICE_ACCOUNT_FILE", GARC_CONFIG_DIR / "service_account.json"))

# All supported scopes for backoffice_agent profile
ALL_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/chat.messages",
    "https://www.googleapis.com/auth/people.readonly",
]

PROFILE_SCOPES = {
    "readonly": [
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/tasks.readonly",
        "https://www.googleapis.com/auth/contacts.readonly",
        "https://www.googleapis.com/auth/documents",
    ],
    "writer": [
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/tasks",
    ],
    "backoffice_agent": ALL_SCOPES,
    "admin": ALL_SCOPES + [
        "https://www.googleapis.com/auth/admin.directory.user.readonly",
    ],
}


def get_credentials(scopes: Optional[list] = None, use_service_account: bool = False):
    """
    Get valid Google credentials.
    Tries: service account → existing token → OAuth flow
    """
    if scopes is None:
        scopes = ALL_SCOPES

    # Service account path
    if use_service_account and SERVICE_ACCOUNT_FILE.exists():
        try:
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_file(
                str(SERVICE_ACCOUNT_FILE), scopes=scopes
            )
            return creds
        except Exception as e:
            print(f"⚠️  Service account error: {e}", file=sys.stderr)

    # User OAuth token
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        creds = None
        if TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), scopes)

        if creds and creds.valid:
            return creds

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                _save_token(creds)
                return creds
            except Exception as e:
                print(f"⚠️  Token refresh failed: {e}", file=sys.stderr)

        # Need fresh OAuth flow
        if not CREDENTIALS_FILE.exists():
            print(f"❌ credentials.json not found: {CREDENTIALS_FILE}", file=sys.stderr)
            print("   Download from Google Cloud Console → APIs & Services → Credentials", file=sys.stderr)
            print("   Run: garc auth login --profile backoffice_agent", file=sys.stderr)
            sys.exit(1)

        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), scopes)
        creds = flow.run_local_server(port=0, open_browser=True)
        _save_token(creds)
        return creds

    except ImportError as e:
        print(f"❌ Missing dependency: {e}", file=sys.stderr)
        print("   Run: pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)


def _save_token(creds):
    """Save credentials to token file."""
    GARC_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())
    TOKEN_FILE.chmod(0o600)


def build_service(service_name: str, version: str, scopes: Optional[list] = None):
    """Build a Google API service with proper credentials."""
    try:
        from googleapiclient.discovery import build
        creds = get_credentials(scopes)
        return build(service_name, version, credentials=creds, cache_discovery=False)
    except ImportError:
        print("❌ google-api-python-client not installed", file=sys.stderr)
        print("   Run: pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)


def with_retry(max_retries: int = 3, backoff: float = 1.5):
    """Decorator: retry on transient Google API errors with exponential backoff."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_str = str(e).lower()
                    # Retry on rate limit, server error
                    if any(code in error_str for code in ["429", "500", "503", "quota", "rate"]):
                        wait = backoff ** attempt
                        if attempt < max_retries - 1:
                            print(f"  ⏳ Rate limit hit, waiting {wait:.1f}s...", file=sys.stderr)
                            time.sleep(wait)
                            last_error = e
                            continue
                    raise
            raise last_error
        return wrapper
    return decorator


def utc_now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_table(rows: list[dict], columns: list[str], max_width: int = 120) -> str:
    """Format a list of dicts as a simple table."""
    if not rows:
        return "(no results)"

    # Calculate column widths
    widths = {col: len(col) for col in columns}
    for row in rows:
        for col in columns:
            val = str(row.get(col, ""))
            widths[col] = min(max(widths[col], len(val)), 40)

    header = "  ".join(col.ljust(widths[col]) for col in columns)
    sep = "  ".join("─" * widths[col] for col in columns)
    lines = [header, sep]
    for row in rows:
        line = "  ".join(str(row.get(col, "")).ljust(widths[col])[:widths[col]] for col in columns)
        lines.append(line)
    return "\n".join(lines)


def load_config() -> dict:
    """Load GARC config from environment / config.env file."""
    config_file = GARC_CONFIG_DIR / "config.env"
    config = {}
    if config_file.exists():
        with open(config_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    config[key.strip()] = val.strip()
    # Override with env vars
    for key in ["GARC_DRIVE_FOLDER_ID", "GARC_SHEETS_ID", "GARC_GMAIL_DEFAULT_TO",
                "GARC_CALENDAR_ID", "GARC_CHAT_SPACE_ID", "GARC_DEFAULT_AGENT"]:
        if os.environ.get(key):
            config[key] = os.environ[key]
    return config
