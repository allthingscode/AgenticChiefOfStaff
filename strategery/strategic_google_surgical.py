"""
STRATEGIC SURGICAL OVERRIDE: Google Tasks & Calendar
Reasoning: The standard 'google-workspace' MCP is unstable and doesn't handle multiple accounts/surgical scopes well.
This script provides direct, credential-locked access to the configured user email for mission-critical scheduling.
"""
import json
import sys
import os
from pathlib import Path
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from fastmcp import FastMCP

# Detect config path
def get_config():
    # Priority: System config, local fallback
    home_config = Path.home() / ".nanobot" / "config.json"
    if home_config.exists():
        with open(home_config, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    return {}

CONFIG = get_config()
STRATEGIC = CONFIG.get("strategic_edition", {})
USER_EMAIL = STRATEGIC.get("user_email", "admin@example.com")

# Use storage_root if available, fallback to ~/.nanobot
_default_root = str(Path.home() / ".nanobot")
STORAGE_ROOT = Path(STRATEGIC.get("storage_root", _default_root))

# Performance Optimization: In-memory service singleton cache
_SERVICE_CACHE = {}

# 1. Credentials Setup
CREDS_DIR = STORAGE_ROOT / "google_surgical" / "credentials"
CREDS_PATH = CREDS_DIR / f"{USER_EMAIL}.json"

def get_service(service_name):
    global _SERVICE_CACHE
    cache_key = f"{service_name}:{USER_EMAIL}"
    
    if cache_key in _SERVICE_CACHE:
        return _SERVICE_CACHE[cache_key]

    if not CREDS_PATH.exists():
        # Fallback to a generic name if specific one doesn't exist
        fallback_path = CREDS_DIR / "default.json"
        if fallback_path.exists():
            path = fallback_path
        else:
            raise Exception(f"Credentials not found at {CREDS_PATH}")
    else:
        path = CREDS_PATH
        
    with open(path, "r") as f:
        data = json.load(f)
    
    creds = Credentials(
        token=data["token"],
        refresh_token=data.get("refresh_token"),
        token_uri=data["token_uri"],
        client_id=data["client_id"],
        client_secret=data["client_secret"],
        scopes=data["scopes"]
    )
    
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        data["token"] = creds.token
        with open(path, "w") as f:
            json.dump(data, f, indent=4)
            
    service = build(service_name, "v1" if service_name == "tasks" else "v3", credentials=creds, static_discovery=True)
    _SERVICE_CACHE[cache_key] = service
    return service

def strategic_merge_calendar_events(all_results, max_results):
    """
    Merges and sorts events from multiple calendars.
    all_results: List of (calendar_name, events_list) tuples.
    """
    merged = []
    for cal_name, events in all_results:
        for ev in events:
            ev["_calendar_name"] = cal_name
            merged.append(ev)
            
    # Sort combined events by start time (dateTime or date)
    merged.sort(key=lambda x: x.get("start", {}).get("dateTime") or x.get("start", {}).get("date") or "")
    return merged[:max_results * 2]

# 2. MCP Server Setup
mcp = FastMCP("Google Surgical")

@mcp.tool()
def list_task_lists():
    """Lists all Google Task lists. Returns a list of task list objects."""
    service = get_service("tasks")
    results = service.tasklists().list().execute()
    return results.get("items", [])

@mcp.tool()
def create_task_list(title: str):
    """Creates a new Google Task list. Requires a title."""
    service = get_service("tasks")
    result = service.tasklists().insert(body={"title": title}).execute()
    return result

@mcp.tool()
def list_tasks(tasklist_id: str = "@default"):
    """Lists tasks in a specific Google Task list."""
    service = get_service("tasks")
    results = service.tasks().list(tasklist=tasklist_id).execute()
    return results.get("items", [])

@mcp.tool()
def create_task(tasklist_id: str, title: str, notes: str = ""):
    """Creates a new task in a specific list."""
    service = get_service("tasks")
    task = {"title": title, "notes": notes}
    result = service.tasks().insert(tasklist=tasklist_id, body=task).execute()
    return result

@mcp.tool()
def list_calendars():
    """Lists all Google Calendars (Read-Only)."""
    service = get_service("calendar")
    results = service.calendarList().list().execute()
    return results.get("items", [])

@mcp.tool()
def list_calendar_events(calendar_id: str = "primary", max_results: int = 10):
    """
    Lists upcoming events from a specific calendar (Read-Only). 
    Use calendar_id='all' to fetch and merge events from ALL available calendars.
    """
    service = get_service("calendar")
    from datetime import UTC
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    
    if calendar_id == "all":
        calendars = list_calendars()
        all_results = []
        for cal in calendars:
            cal_id = cal.get("id")
            cal_name = cal.get("summary", "Unknown")
            try:
                results = service.events().list(
                    calendarId=cal_id, timeMin=now, maxResults=max_results, 
                    singleEvents=True, orderBy='startTime'
                ).execute()
                all_results.append((cal_name, results.get("items", [])))
            except Exception:
                continue
        return strategic_merge_calendar_events(all_results, max_results)
    else:
        results = service.events().list(
            calendarId=calendar_id, timeMin=now, maxResults=max_results, 
            singleEvents=True, orderBy='startTime'
        ).execute()
        return results.get("items", [])

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "mcp_wrapper":
        mcp.run()
    elif len(sys.argv) > 1 and sys.argv[1] == "check_creds":
        print(f"Checking credentials for {USER_EMAIL}...")
        try:
            get_service("tasks")
            print("[PASS] Credentials valid and service initialized.")
        except Exception as e:
            print(f"[FAIL] Credential check failed: {e}")
    else:
        print("Run with 'mcp_wrapper' to start the MCP server.")
