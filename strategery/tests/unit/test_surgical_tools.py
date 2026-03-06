import pytest
from unittest.mock import patch, MagicMock, mock_open
import json
import os
import sys
from pathlib import Path

# Import tools
import strategery.strategic_google_surgical as google_tool

@pytest.fixture(autouse=True)
def clear_cache():
    google_tool._SERVICE_CACHE.clear()
    yield

def test_strategic_merge_calendar_events():
    """Verify that multiple calendar results are correctly merged and sorted."""
    all_results = [
        ("Work", [
            {"summary": "Work Meet", "start": {"dateTime": "2026-03-05T10:00:00Z"}},
            {"summary": "Work Deep", "start": {"dateTime": "2026-03-05T14:00:00Z"}},
        ]),
        ("Personal", [
            {"summary": "Gym", "start": {"dateTime": "2026-03-05T08:00:00Z"}},
            {"summary": "Dinner", "start": {"date": "2026-03-05"}}, # All-day event
        ])
    ]
    
    merged = google_tool.strategic_merge_calendar_events(all_results, max_results=5)
    
    # Sort order:
    # 1. "2026-03-05" (Dinner - all day) comes first in lexicographical sort against ISO strings
    # 2. "2026-03-05T08..." (Gym)
    # 3. "2026-03-05T10..." (Work Meet)
    # 4. "2026-03-05T14..." (Work Deep)
    
    assert len(merged) == 4
    assert merged[0]["summary"] == "Dinner"
    assert merged[1]["summary"] == "Gym"
    assert merged[2]["summary"] == "Work Meet"
    assert merged[3]["summary"] == "Work Deep"

@pytest.mark.asyncio
async def test_google_surgical_list_calendar_events_all_merge():
    """Verify that list_calendar_events('all') triggers the merge logic."""
    mock_service = MagicMock()
    # Mock list_calendars results
    mock_service.calendarList().list().execute.return_value = {"items": [{"id": "c1", "summary": "Cal1"}]}
    # Mock events list results
    mock_service.events().list().execute.return_value = {"items": [{"summary": "Event1", "start": {"date": "2026-03-05"}}]}
    
    with patch("strategery.strategic_google_surgical.get_service", return_value=mock_service), \
         patch("strategery.strategic_google_surgical.strategic_merge_calendar_events") as mock_merge:
        
        google_tool.list_calendar_events("all", 10)
        
        # Verify it merged the results
        mock_merge.assert_called_once()
        args, _ = mock_merge.call_args
        assert args[0][0][0] == "Cal1"

def test_google_surgical_credential_fallback(tmp_path):
    """Verify that get_service falls back to default.json if specific email creds missing."""
    # We must patch both STORAGE_ROOT and the calculated CREDS_PATH/CREDS_DIR in the module
    creds_dir = tmp_path / "google_surgical" / "credentials"
    creds_dir.mkdir(parents=True)
    default_json = creds_dir / "default.json"
    
    creds_data = {"token": "t", "token_uri": "u", "client_id": "c", "client_secret": "s", "scopes": ["sc"]}
    default_json.write_text(json.dumps(creds_data))
    
    # Update module-level globals for this test
    with patch("strategery.strategic_google_surgical.CREDS_DIR", creds_dir), \
         patch("strategery.strategic_google_surgical.CREDS_PATH", creds_dir / "unknown@example.com.json"), \
         patch("strategery.strategic_google_surgical.USER_EMAIL", "unknown@example.com"):
        
        with patch("strategery.strategic_google_surgical.Credentials") as mock_creds_class, \
             patch("strategery.strategic_google_surgical.build"):
            
            mock_creds = MagicMock()
            mock_creds.expired = False
            mock_creds_class.return_value = mock_creds
            
            google_tool.get_service("tasks")
            # Should not raise exception because default.json exists
            assert mock_creds_class.called

def test_google_surgical_create_task():
    """Verify create_task calls the correct API method with body."""
    mock_service = MagicMock()
    mock_insert = MagicMock()
    mock_service.tasks.return_value.insert.return_value = mock_insert
    
    with patch("strategery.strategic_google_surgical.get_service", return_value=mock_service):
        google_tool.create_task("mylist", "Task Title", "Some notes")
        
        mock_service.tasks.return_value.insert.assert_called_with(
            tasklist="mylist",
            body={"title": "Task Title", "notes": "Some notes"}
        )
