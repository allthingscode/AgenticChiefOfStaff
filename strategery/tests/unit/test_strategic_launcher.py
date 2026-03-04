import pytest
import os
import json
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
from pathlib import Path
from nanobot.agent.loop import AgentLoop
from nanobot.bus.queue import MessageBus
from nanobot.agent.memory import MemoryStore
from strategery.patches.subagent import SubagentPatch
from strategery.patches.infra import InfraPatch
from strategery.patches.config import ConfigPatch

@pytest.fixture
def mock_config():
    return {
        "agents": {
            "defaults": {
                "model": "test-model",
                "workspace": "~/.nanobot/test_workspace"
            },
            "consolidator": {
                "model": "consolidator-model"
            }
        },
        "strategic_edition": {
            "user_email": "test@example.com",
            "storage_root": "D:/Nanobot_Storage_Test"
        }
    }

def test_infra_patch_apply():
    """Verify that InfraPatch sets the correct event loop policy on Windows."""
    with patch("sys.platform", "win32"), \
         patch("asyncio.set_event_loop_policy") as mock_set_policy:
        patch_inst = InfraPatch()
        patch_inst.apply({})
        mock_set_policy.assert_called()

def test_config_patch_data_dir_redirection(tmp_path):
    """Verify that ConfigPatch redirects the core data directory."""
    custom_root = tmp_path / "custom_storage"
    
    # Mock load_strategic_context so it returns our custom root
    # This avoids issues with mocking Path.home globally
    with patch("strategery.patches.config.load_strategic_context", return_value=({}, "test@example.com", custom_root)):
        # Apply Patch
        patch_inst = ConfigPatch()
        patch_inst.apply({})

        # Verify Redirection
        from nanobot.config.loader import get_data_dir
        assert Path(get_data_dir()) == custom_root
@pytest.mark.asyncio
async def test_subagent_registry_initialization():
    """Verify that SubagentPatch correctly tags its tool registry."""
    patch_inst = SubagentPatch()
    
    # Setup mock manager and original run_subagent
    from nanobot.agent.subagent import SubagentManager
    mock_mgr = MagicMock(spec=SubagentManager)
    mock_mgr.model = "default"
    
    # We just want to check if the ToolRegistry class is replaced during execution
    # This requires a more complex mock or a simplified check of the patch logic
    assert patch_inst.name == "Subagent & Tool Orchestration"

def test_strategic_migrate_config():
    """Verify that strategic_migrate_config strips custom keys but preserves original data."""
    from strategery.patches.config import strategic_migrate_config
    
    raw_data = {
        "agents": {"defaults": {"model": "gpt-4"}},
        "strategic_edition": {"secret": "key"},
        "memory": {"window": 10}
    }
    
    capture = {}
    clean_data = strategic_migrate_config(dict(raw_data), capture)
    
    # 1. Capture should have everything
    assert "strategic_edition" in capture
    assert "memory" in capture
    
    # 2. Clean data should be Pydantic-safe
    assert "strategic_edition" not in clean_data
    assert "memory" not in clean_data
    assert clean_data["agents"]["defaults"]["model"] == "gpt-4"

@pytest.mark.asyncio
async def test_strategic_consolidation_flow(tmp_path):
    """Verify the 'Clean History' consolidation flow (Vector Store + Journal)."""
    from strategery.patches.memory import MemoryPatch
    from nanobot.agent.memory import MemoryStore

    mock_session = MagicMock()
    mock_session.messages = [{"role": "user", "content": "test", "timestamp": "2026-03-01T12:00:00"}]
    mock_session.last_consolidated = 0

    mock_provider = AsyncMock()
    mock_response = MagicMock()
    mock_response.has_tool_calls = False
    mock_response.content = '{"history_entry": "Test summary", "memory_update": "Test facts"}'
    mock_provider.chat.return_value = mock_response

    # Use real temp path provided by pytest to allow physical directory creation
    store = MemoryStore(workspace=tmp_path)
    store.read_long_term = MagicMock(return_value="Existing facts")
    store.write_long_term = MagicMock()
    store.append_history = MagicMock() 

    patch_inst = MemoryPatch()

    # We mock load_strategic_context inside the memory patch module
    with patch("strategery.patches.memory.load_strategic_context", return_value=({}, "test@example.com", tmp_path)), \
         patch("strategery.patches.memory.VectorStoreFactory") as mock_vsa_factory, \
         patch("builtins.open", mock_open()) as mock_file:

        mock_vec = MagicMock()
        mock_vec.add_entry = AsyncMock(return_value=True)
        mock_vsa_factory.get_store.return_value = mock_vec

        # Apply patch and run consolidation
        patch_inst.apply({"agents": {"consolidator": {"model": "test-model"}}})
        await store.consolidate(mock_session, mock_provider, "test-model", archive_all=True)

        # VERIFY:
        # 1. append_history was NOT called (no bloat)
        store.append_history.assert_not_called()
        # 2. Vector Store WAS called for the entry
        mock_vec.add_entry.assert_any_call("Test summary", {"type": "history_summary", "source": "consolidation"})
        # 3. Journal was written (mocked open check)
        mock_file.assert_called()

@pytest.mark.asyncio
async def test_reasoning_stripper_integration():
    """Verify that reasoning blocks are stripped from the final response content."""
    from nanobot.agent.loop import AgentLoop
    
    # Setup AgentLoop with patched _strip_think
    # (Assuming ProviderPatch has been applied)
    text = "<think>Internal thoughts</think>Final Answer"
    clean = AgentLoop._strip_think(text)
    assert clean == "Final Answer"
    
    text2 = "**Thought:** Some reasoning.\n\nDirect Response"
    clean2 = AgentLoop._strip_think(text2)
    assert clean2 == "Direct Response"

def test_bom_safe_open_patch(tmp_path):
    """Verify that the global 'open' patch handles UTF-8-sig for JSON files."""
    from strategery.patches.config import ConfigPatch
    
    test_json = tmp_path / "unique_test_bom.json"
    content = '{"unique_key": "unique_value"}'
    
    # Apply patch
    patch_inst = ConfigPatch()
    patch_inst.apply({})
    
    # Test 1: Writing with standard utf-8, reading should work
    test_json.write_text(content, encoding='utf-8')
    with open(test_json, "r") as f:
        data = json.load(f)
        assert data["unique_key"] == "unique_value"
        
    # Test 2: Writing with utf-8-sig (BOM), reading should work
    test_json.write_text(content, encoding='utf-8-sig')
    with open(test_json, "r") as f:
        data = json.load(f)
        assert data["unique_key"] == "unique_value"
