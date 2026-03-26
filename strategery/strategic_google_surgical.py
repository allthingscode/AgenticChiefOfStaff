"""
STRATEGIC SURGICAL OVERRIDE: Google Tasks, Calendar & Drive (Backup Edition)
Reasoning: The standard 'google-workspace' MCP is unstable. This script provides direct, 
credential-locked access for scheduling and secure cloud backups.
"""
import json
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import FastMCP
from google.auth.transport.requests import Request

# MANDATE (F-014): Added Drive scope for sandboxed backup management
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


# Detect config path
def get_config():
    home_config = Path.home() / ".nanobot" / "config.json"
    if home_config.exists():
        with open(home_config, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    return {}

CONFIG = get_config()
STRATEGIC = CONFIG.get("strategic_edition", {})
USER_EMAIL = STRATEGIC.get("user_email", "admin@example.com")
_default_root = str(Path.home() / ".nanobot")
STORAGE_ROOT = Path(STRATEGIC.get("storage_root", _default_root))

# Performance Optimization: In-memory service singleton cache
_SERVICE_CACHE = {}

# 1. Credentials Setup (Standardized on C: drive)
CREDS_DIR = Path.home() / ".nanobot" / "google_surgical" / "credentials"
CREDS_PATH = CREDS_DIR / f"{USER_EMAIL}.json"

# MANDATE (F-014): Added Drive scope for sandboxed backup management
SCOPES = [
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/drive.file"
]

def get_service(service_name, version='v1', force_reauth=False):
    """Returns a cached or new Google API service instance."""
    cache_key = f"{service_name}_{version}_{USER_EMAIL}"
    if not force_reauth and cache_key in _SERVICE_CACHE:
        return _SERVICE_CACHE[cache_key]

    creds = None
    if not force_reauth and CREDS_PATH.exists():
        with open(CREDS_PATH, "r") as f:
            data = json.load(f)
        creds = Credentials(
            token=data["token"],
            refresh_token=data.get("refresh_token"),
            token_uri=data["token_uri"],
            client_id=data["client_id"],
            client_secret=data["client_secret"],
            scopes=data.get("scopes", SCOPES)
        )
    elif not force_reauth:
        # Fallback to default.json for test compatibility (BUG-093)
        default_path = CREDS_DIR / "default.json"
        if default_path.exists():
            with open(default_path, "r") as f:
                data = json.load(f)
            creds = Credentials(
                token=data["token"],
                refresh_token=data.get("refresh_token"),
                token_uri=data["token_uri"],
                client_id=data["client_id"],
                client_secret=data["client_secret"],
                scopes=data.get("scopes", SCOPES)
            )

    needs_auth = False
    if force_reauth or not creds or not all(s in creds.scopes for s in SCOPES):
        needs_auth = True
    else:
        try:
            if not creds.valid:
                if creds.refresh_token:
                    creds.refresh(Request())
                else:
                    needs_auth = True
        except Exception:
            needs_auth = True

    if needs_auth:
        if os.environ.get("PYTEST_CURRENT_TEST"):
            raise Exception("Auth required but disabled in test mode.")

        from google_auth_oauthlib.flow import InstalledAppFlow
        client_secrets = CREDS_DIR / "client_secrets.json"
        if not client_secrets.exists():
            raise FileNotFoundError(f"Missing client_secrets.json at {client_secrets}")

        flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), SCOPES)

        # Check if we should use console flow (useful for remote sessions or headless)
        if "--console" in sys.argv:
            creds = flow.run_local_server(port=0, open_browser=False)
        else:
            creds = flow.run_local_server(port=0)

        with open(CREDS_PATH, "w") as f:
            f.write(creds.to_json())

    service = build(service_name, version, credentials=creds)
    _SERVICE_CACHE[cache_key] = service
    return service

def strategic_merge_calendar_events(results_list, max_results=10):
    """Merges and sorts events from multiple calendars by start time."""
    merged = []
    for cal_name, events in results_list:
        for event in events:
            # Tag the event with its source calendar for transparency
            event["_calendar"] = cal_name
            merged.append(event)

    def get_start(event):
        start = event.get('start', {})
        dt = start.get('dateTime')
        if dt:
            return dt
        # All-day events (date only) get a suffix to sort after timed events of the same day
        return (start.get('date') or '0000-00-00') + 'T23:59:59Z'

    merged.sort(key=get_start)
    return merged[:max_results]

mcp = FastMCP("Google Surgical")

@mcp.tool()
async def list_calendar_events(calendar_id: str = "primary", max_results: int = 10):
    """Lists upcoming events from the specified calendar (or 'all')."""
    if calendar_id == "all":
        # 1. Get all calendars
        service = get_service('calendar', 'v3')
        cal_list = service.calendarList().list().execute()
        all_calendars = cal_list.get('items', [])

        # 2. Fetch events from each
        all_results = []
        for cal in all_calendars:
            try:
                events = await list_calendar_events(cal['id'], max_results=max_results)
                if events:
                    all_results.append((cal.get('summary', 'Unknown'), events))
            except Exception:
                continue

        # 3. Merge and sort
        return strategic_merge_calendar_events(all_results, max_results=max_results)

    service = get_service('calendar', 'v3')
    now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    events_result = service.events().list(calendarId=calendar_id, timeMin=now,
                                        maxResults=max_results, singleEvents=True,
                                        orderBy='startTime').execute()
    return events_result.get('items', [])

@mcp.tool()
async def list_task_lists():
    """Lists all task lists for the current user."""
    service = get_service('tasks', 'v1')
    results = service.tasklists().list().execute()
    return results.get('items', [])

@mcp.tool()
async def list_tasks(tasklist_id: str = "@default"):
    """Lists tasks from a specific task list."""
    service = get_service('tasks', 'v1')
    results = service.tasks().list(tasklist=tasklist_id).execute()
    return results.get('items', [])

@mcp.tool()
async def create_task(tasklist_id: str, title: str, notes: str = None):
    """Creates a new task in the specified list."""
    service = get_service('tasks', 'v1')
    task = {'title': title, 'notes': notes}
    result = service.tasks().insert(tasklist=tasklist_id, body=task).execute()
    return f"Task created: {result.get('title')} (ID: {result.get('id')})"

@mcp.tool()
async def google_drive_upload(local_path: str, filename: str, parent_id: str = None):
    """Uploads a local file to Google Drive. (F-014)"""
    from googleapiclient.http import MediaFileUpload
    service = get_service('drive', 'v3')

    # Use backup_folder_id from config as default if not provided
    target_folder = parent_id or STRATEGIC.get("backup_folder_id")

    file_metadata = {'name': filename}
    if target_folder:
        file_metadata['parents'] = [target_folder]

    media = MediaFileUpload(local_path, resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return f"Uploaded successfully to {target_folder or 'Root'}. File ID: {file.get('id')}"

@mcp.tool()
async def google_drive_list(query: str = "name contains 'nanobot_backup_'"):
    """Lists files created by this app matching the query."""
    service = get_service('drive', 'v3')
    results = service.files().list(q=query, spaces='drive',
                                 fields='files(id, name, createdTime)',
                                 orderBy='createdTime desc').execute()
    return results.get('files', [])

@mcp.tool()
async def google_drive_delete(file_id: str):
    """Deletes a file by ID (SAFETY: Only allows files created by this app)."""
    service = get_service('drive', 'v3')
    # Double-check metadata before deletion
    file = service.files().get(fileId=file_id, fields='name').execute()
    if not file.get('name', '').startswith('nanobot_backup_'):
        return "ERROR: Safety violation. This tool can only delete 'nanobot_backup_' files."

    service.files().delete(fileId=file_id).execute()
    return f"Deleted file: {file.get('name')}"

@mcp.tool()
async def package_strategic_archive(zip_name: str, includes: list[str], excludes: list[str]):
    """Creates a filtered ZIP archive of strategic data. (F-014)"""
    temp_zip = STORAGE_ROOT / zip_name

    def should_exclude(path):
        p_str = str(path).replace('\\', '/')
        for ex in excludes:
            if ex.lower() in p_str.lower():
                return True
        return False

    with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for include_path in includes:
            path = Path(include_path)
            if not path.exists(): continue

            if path.is_file():
                if not should_exclude(path):
                    zipf.write(path, path.relative_to(path.parent))
            else:
                for root, _dirs, files in os.walk(path):
                    for file in files:
                        file_path = Path(root) / file
                        if not should_exclude(file_path):
                            # Maintain structure relative to the include root
                            arcname = file_path.relative_to(path.parent)
                            zipf.write(file_path, arcname)

    return str(temp_zip)

if __name__ == "__main__":
    if "--reauth" in sys.argv:
        print("Initiating Strategic Google Re-authentication...")
        # MANDATE (F-014): Specify v3 for Drive to avoid 'Unknown API' errors
        get_service('drive', version='v3', force_reauth=True)
        print("\nSUCCESS: Authentication flow complete. Credentials updated at:")
        print(CREDS_PATH)
        sys.exit(0)

    mcp.run()
