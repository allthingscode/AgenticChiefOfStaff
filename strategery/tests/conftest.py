import os
import sys
import json
from pathlib import Path

# SET UP TEST ENVIRONMENT VARIABLES BEFORE ANY IMPORTS
# This prevents strategic_logger from creating ./logs/ in the project root
# We derive it manually to avoid triggering strategic patch initialization.
try:
    home_config = Path.home() / ".nanobot" / "config.json"
    storage_root = Path.home() / ".nanobot" / "storage"
    if home_config.exists():
        with open(home_config, "r", encoding="utf-8-sig") as f:
            raw = json.load(f)
            strat = raw.get("strategic_edition", {})
            if s_root := strat.get("storage_root"):
                storage_root = Path(s_root)
    
    # User requested derivation: D:\Test_Workspace\logs
    # storage_root is typically D:\Nanobot_Storage
    TEST_WORKSPACE = storage_root.parent / "Test_Workspace"
    os.environ["STRATEGIC_LOG_DIR"] = str(TEST_WORKSPACE / "logs")
except Exception:
    # Fallback to literal if derivation fails
    os.environ["STRATEGIC_LOG_DIR"] = "D:/Test_Workspace/logs"

import pytest
from unittest.mock import patch, MagicMock

# Use relative imports based on the strategery test structure
from strategery.tests.mocks.mock_config import get_mock_config_json

@pytest.fixture(autouse=True)
def global_config_patch():
    with patch("builtins.open", MagicMock()) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = get_mock_config_json()
        yield mock_open

@pytest.fixture
def drive_service():
    from strategery.tests.mocks.mock_google_drive import get_mock_drive_service
    mock_svc = get_mock_drive_service()
    with patch("googleapiclient.discovery.build", return_value=mock_svc):
        yield mock_svc
