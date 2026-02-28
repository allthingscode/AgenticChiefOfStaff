import pytest
from unittest.mock import patch, MagicMock, mock_open
import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import tools WITHOUT global mocks
import strategery.strategic_google_surgical as google_tool
import strategery.strategic_email_reporter as email_tool

@pytest.fixture
def mock_creds_data():
    return {
        "token": "test-token",
        "refresh_token": "test-refresh",
        "token_uri": "test-uri",
        "client_id": "test-client",
        "client_secret": "test-secret",
        "scopes": ["scope1"]
    }

def test_google_surgical_get_service(mock_creds_data):
    """Verify get_service initializes correctly with credentials."""
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_creds_data))):
            # We use a MagicMock for the Credentials INSTANCE, but we must
            # mock the CLASS in the tool's namespace.
            mock_creds = MagicMock()
            mock_creds.expired = False
            
            # Patch the Credentials CLASS in the google_tool module
            with patch("strategery.strategic_google_surgical.Credentials", return_value=mock_creds):
                # We must patch 'build' in the google_tool namespace to avoid 
                # its real implementation trying to parse our mock data.
                with patch("strategery.strategic_google_surgical.build") as mock_build:
                    google_tool.get_service("tasks")
                    
                    mock_build.assert_called_with("tasks", "v1", credentials=mock_creds)

def test_google_surgical_list_tasks():
    """Verify list_tasks calls the correct API method."""
    mock_service = MagicMock()
    mock_list_req = MagicMock()
    mock_service.tasks.return_value.list.return_value = mock_list_req
    mock_list_req.execute.return_value = {"items": [{"id": "task1", "title": "Test Task"}]}
    
    with patch("strategery.strategic_google_surgical.get_service", return_value=mock_service):
        results = google_tool.list_tasks("mylist")
        
        assert len(results) == 1
        assert results[0]["id"] == "task1"
        mock_service.tasks.assert_called_with()
        mock_service.tasks.return_value.list.assert_called_with(tasklist="mylist")

def test_email_reporter_send_success():
    """Verify email reporter sends correctly via Gmail API."""
    mock_service = MagicMock()
    mock_send_req = MagicMock()
    mock_service.users.return_value.messages.return_value.send.return_value = mock_send_req
    mock_send_req.execute.return_value = {"id": "msg123"}
    
    with patch("strategery.strategic_email_reporter.get_gmail_service", return_value=mock_service):
        email_tool.USER_EMAIL = "admin@example.com"
        result = email_tool.send_email_report("Test Subject", "Test Body")
        
        assert "sent successfully" in result
        assert "msg123" in result
        mock_service.users.return_value.messages.return_value.send.assert_called_once()
        _, kwargs = mock_service.users.return_value.messages.return_value.send.call_args
        assert kwargs["userId"] == "me"

def test_email_reporter_failure():
    """Verify error handling in email reporter."""
    with patch("strategery.strategic_email_reporter.get_gmail_service", side_effect=Exception("API Error")):
        result = email_tool.send_email_report("Subject", "Body")
        assert "Failed to send email: API Error" in result
