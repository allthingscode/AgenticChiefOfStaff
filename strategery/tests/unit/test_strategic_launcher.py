import pytest
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from strategery.strategic_launcher import pre_start_cleanup, warmup_vector_store, transform_args

def test_transform_args_default():
    """Verify that transform_args defaults to 'nanobot gateway'."""
    args = ["strategic_launcher.py"]
    new_args = transform_args(args)
    assert new_args == ["nanobot", "gateway"]

def test_transform_args_passthrough():
    """Verify that transform_args passes through arguments to nanobot."""
    args = ["strategic_launcher.py", "status"]
    new_args = transform_args(args)
    assert new_args == ["nanobot", "status"]

def test_pre_start_cleanup_deletes_files(tmp_path):
    """Verify that cleanup unlinks targeted files."""
    # Setup mock workspace and files
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    temp_file = workspace / "test.tmp"
    temp_file.write_text("dummy")
    
    mcp_dir = Path.home() / ".google_workspace_mcp"
    mcp_file = mcp_dir / "temp_session.json"
    
    with patch("pathlib.Path.home", return_value=tmp_path):
        # We need to recreate the mcp_dir under the mocked home
        mcp_dir_mocked = tmp_path / ".google_workspace_mcp"
        mcp_dir_mocked.mkdir()
        mcp_file_mocked = mcp_dir_mocked / "temp_session.json"
        mcp_file_mocked.write_text("dummy")
        
        config = {"agents": {"defaults": {"workspace": str(workspace)}}}
        
        success = pre_start_cleanup(config=config)
        
        assert success is True
        assert not temp_file.exists()
        assert not mcp_file_mocked.exists()

def test_warmup_vector_store_success(tmp_path):
    """Verify that warmup_vector_store attempts to initialize the store."""
    with patch("strategery.patches.vector_store.StrategicVectorStore") as mock_vsa:
        success = warmup_vector_store(storage_root=tmp_path)
        assert success is True
        mock_vsa.assert_called_once()

def test_warmup_vector_store_failure():
    """Verify that warmup_vector_store handles errors gracefully."""
    with patch("strategery.patches.vector_store.StrategicVectorStore", side_effect=Exception("Chroma Error")):
        # Should return False but NOT raise
        success = warmup_vector_store()
        assert success is False
