import json
from unittest.mock import MagicMock, patch

import pytest

import strategery.strategic_google_surgical as google_tool


@pytest.fixture(autouse=True)
def clear_cache():
    google_tool._SERVICE_CACHE.clear()

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

    assert len(merged) == 4
    assert merged[0]["summary"] == "Gym"       # 08:00
    assert merged[1]["summary"] == "Work Meet" # 10:00
    assert merged[2]["summary"] == "Work Deep" # 14:00
    assert merged[3]["summary"] == "Dinner"    # All-day (sorted last for the day)
    assert merged[0]["_calendar"] == "Personal"

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

        await google_tool.list_calendar_events("all", 10)

        # Verify it merged the results
        mock_merge.assert_called_once()

def test_google_surgical_credential_fallback(tmp_path):
    """Verify that get_service falls back to default.json if specific email creds missing."""
    # We must patch both STORAGE_ROOT and the calculated CREDS_PATH/CREDS_DIR in the module
    creds_dir = tmp_path / "google_surgical" / "credentials"
    creds_dir.mkdir(parents=True)
    default_json = creds_dir / "default.json"

    # Minimal credential structure that looks valid to the Credentials constructor
    creds_data = {
        "token": "t",
        "refresh_token": "rt",
        "token_uri": "u",
        "client_id": "c",
        "client_secret": "s",
        "scopes": google_tool.SCOPES
    }
    default_json.write_text(json.dumps(creds_data))

    # Update module-level globals for this test
    with patch("strategery.strategic_google_surgical.CREDS_DIR", creds_dir), \
         patch("strategery.strategic_google_surgical.CREDS_PATH", creds_dir / "unknown@example.com.json"), \
         patch("strategery.strategic_google_surgical.USER_EMAIL", "unknown@example.com"):

        with patch("strategery.strategic_google_surgical.Credentials", wraps=google_tool.Credentials), \
             patch("strategery.strategic_google_surgical.build"):

            # Calling get_service should now find default.json and NOT trigger auth
            service = google_tool.get_service("tasks")
            assert service is not None

@pytest.mark.asyncio
async def test_google_surgical_create_task():
    """Verify create_task calls the correct API method with body."""
    mock_service = MagicMock()
    mock_insert = MagicMock()
    mock_service.tasks.return_value.insert.return_value = mock_insert

    with patch("strategery.strategic_google_surgical.get_service", return_value=mock_service):
        await google_tool.create_task("mylist", "Task Title", "Some notes")

        mock_service.tasks.return_value.insert.assert_called_with(
            tasklist="mylist",
            body={"title": "Task Title", "notes": "Some notes"}
        )
