import os
import sys
import json
from pathlib import Path
import builtins

# SET UP TEST ENVIRONMENT VARIABLES BEFORE ANY IMPORTS
try:
    home_config = Path.home() / ".nanobot" / "config.json"
    storage_root = Path.home() / ".nanobot" / "storage"
    if home_config.exists():
        with open(home_config, "r", encoding="utf-8-sig") as f:
            raw = json.load(f)
            strat = raw.get("strategic_edition", {})
            if s_root := strat.get("storage_root"):
                storage_root = Path(s_root)
    
    TEST_WORKSPACE = storage_root.parent / "Test_Workspace"
    os.environ["STRATEGIC_LOG_DIR"] = str(TEST_WORKSPACE / "logs")
except Exception:
    os.environ["STRATEGIC_LOG_DIR"] = "D:/Test_Workspace/logs"

import pytest
from unittest.mock import patch, MagicMock
from strategery.patches.base import PatchContext
from strategery.tests.mocks.mock_config import get_mock_config_json
from strategery.logic.config_logic import validate_strategic_config

@pytest.fixture
def mock_context(tmp_path):
    """Provides a valid PatchContext object for unit tests."""
    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    (storage_root / "workspace").mkdir()
    
    # Validate the mock JSON against the Strategic Schema
    raw_config = json.loads(get_mock_config_json())
    config = validate_strategic_config(raw_config)
    
    return PatchContext(
        config=config,
        storage_root=storage_root,
        user_email="test@user.com",
        app_root=Path(__file__).parent.parent.parent
    )

@pytest.fixture(autouse=True)
def global_config_patch():
    """
    Surgical patch for config files only. 
    Allows other files (like test temp files) to be read normally.
    """
    orig_open = builtins.open
    
    def side_effect(file, *args, **kwargs):
        f_str = str(file).lower()
        # Mock only the central config and jobs files
        if f_str.endswith("config.json") or f_str.endswith("jobs.json"):
            m = MagicMock()
            m.__enter__.return_value.read.return_value = get_mock_config_json()
            return m
        return orig_open(file, *args, **kwargs)

    with patch("builtins.open", side_effect=side_effect):
        yield

# BUG-223: Resiliency patch for crewai.llm.FilteredStream.isatty
# Prevents 'ValueError: I/O operation on closed file' during atexit/teardown.
def pytest_configure(config):
    try:
        from crewai.llm import FilteredStream
        _orig_isatty = FilteredStream.isatty
        def _safe_isatty(self):
            try:
                # If the original stream is closed, return False instead of raising ValueError
                if hasattr(self, "_original_stream") and self._original_stream.closed:
                    return False
                return _orig_isatty(self)
            except ValueError:
                return False
        FilteredStream.isatty = _safe_isatty
    except ImportError:
        pass # CrewAI not installed or different version
