import pytest
from unittest.mock import patch, MagicMock, AsyncMock, mock_open
import json
import os
import sys
import asyncio
from pathlib import Path

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the patches
import strategery.patches.config as config_patch
import strategery.patches.infra as infra_patch
import strategery.patches.memory as memory_patch
import strategery.patches.provider as provider_patch
import strategery.patches.subagent as subagent_patch
import strategery.patches.telegram as telegram_patch

import nanobot.config.loader
import nanobot.agent.tools.registry
import nanobot.agent.subagent

@pytest.fixture
def mock_config_data():
    return {
        "strategic_edition": {
            "user_email": "test@example.com",
            "storage_root": "D:/Test_Storage"
        },
        "agents": {
            "defaults": {
                "compaction": {"enabled": True},
                "contextPruning": {"enabled": True},
                "memorySearch": {"enabled": True}
            },
            "consolidator": {"model": "gemini-1.5-pro-test"},
            "specialists": {
                "researcher": {"model": "gemini-1.5-pro", "keywords": ["research"]}
            }
        },
        "memory": {"some": "data"}
    }

def test_config_migration_patch(mock_config_data):
    """Verify that ConfigPatch correctly strips custom keys."""
    patch_inst = config_patch.ConfigPatch()
    
    # We need to capture what _patched_migrate does
    # Since apply() actually performs the monkey-patch, we can trigger it
    raw_capture = {}
    patch_inst.apply(raw_capture)
    
    # Trigger the patched migrate
    data = nanobot.config.loader._migrate_config(mock_config_data.copy())
    
    # Verify custom keys are stripped
    assert "strategic_edition" not in data
    assert "memory" not in data
    assert "compaction" not in data["agents"]["defaults"]
    assert "contextPruning" not in data["agents"]["defaults"]
    
    # Verify RAW_CONFIG (captured in raw_capture) was populated
    assert raw_capture["strategic_edition"]["user_email"] == "test@example.com"

@pytest.mark.asyncio
async def test_litellm_logging_patch():
    """Verify LiteLLMProvider.chat is patched to log the request."""
    from nanobot.providers.litellm_provider import LiteLLMProvider
    
    patch_inst = provider_patch.ProviderPatch()
    patch_inst.apply({})
    
    mock_self = MagicMock(spec=LiteLLMProvider)
    mock_self.default_model = "test-model"
    
    # Mock the original chat method
    with patch.object(LiteLLMProvider, "_orig_chat_strategic", new_callable=AsyncMock) as mock_orig:
        from loguru import logger
        with patch.object(logger, "info") as mock_logger:
            # Call the patched method directly through the class to ensure it's hit
            await LiteLLMProvider.chat(mock_self, messages=[{"role": "user", "content": "hi"}])
            
            mock_logger.assert_called_with("[Strategic] LiteLLM request: model={}", "test-model")
            mock_orig.assert_called_once()

def test_heartbeat_init_patch():
    """Verify HeartbeatService model is overridden from config."""
    config_data = {
        "agents": {
            "heartbeat": {"model": "fast-model-override"}
        }
    }
    
    patch_inst = subagent_patch.SubagentPatch()
    patch_inst.apply(config_data)
    
    from nanobot.heartbeat.service import HeartbeatService
    
    mock_orig_init = MagicMock()
    with patch.object(HeartbeatService, "_orig_hb_init_strategic", mock_orig_init):
        mock_self = MagicMock()
        # Trigger the patched __init__
        HeartbeatService.__init__(mock_self, "bus", "original-model")
        
        args, _ = mock_orig_init.call_args
        assert args[1] == "fast-model-override"

@pytest.mark.asyncio
async def test_google_hammer_mcp_patch():
    """Verify ToolRegistry.execute forces the user email for google-surgical tools."""
    # SubagentPatch needs USER_EMAIL from config.load_strategic_context
    with patch("strategery.patches.config.load_strategic_context", return_value=({}, "forced@example.com", Path("/tmp"))):
        patch_inst = subagent_patch.SubagentPatch()
        patch_inst.apply({})
    
    from nanobot.agent.tools.registry import ToolRegistry
    
    with patch.object(ToolRegistry, "_orig_tool_execute_strategic", new_callable=AsyncMock) as mock_orig:
        args = {"user_google_email": "someone@else.com", "other": "param"}
        mock_registry = MagicMock()
        await ToolRegistry.execute(mock_registry, "mcp_google-surgical_create_task", args)
        
        mock_orig.assert_called_once()
        name_arg, call_args = mock_orig.call_args[0]
        assert call_args["user_google_email"] == "forced@example.com"

@pytest.mark.asyncio
async def test_specialist_routing_logic():
    """Verify that the specialist model is correctly selected based on keywords."""
    config_data = {
        "agents": {
            "specialists": {
                "researcher": {"model": "powerful-model", "keywords": ["find", "search"]},
                "architect": {"model": "design-model", "keywords": ["design"]}
            }
        }
    }
    
    patch_inst = subagent_patch.SubagentPatch()
    # Need to mock the hammer part of apply
    with patch("strategery.patches.config.load_strategic_context", return_value=({}, "em", Path("p"))):
        patch_inst.apply(config_data)
    
    from nanobot.agent.subagent import SubagentManager
    mock_manager = MagicMock(spec=SubagentManager)
    mock_manager.model = "default-model"
    
    # Mock the original run method
    async def mock_run(self, task_id, task, label, origin):
        return self.model # Return the model state at time of call

    with patch.object(SubagentManager, "_orig_run_subagent_strategic", mock_run):
        # We need to call the patched method. Since it's an instance method, we pass mock_manager
        result_model = await SubagentManager._run_subagent(mock_manager, "id", "find the documents", "label", "origin")
        
        assert result_model == "powerful-model"
        # Verify it restored the model
        assert mock_manager.model == "default-model"

@pytest.mark.asyncio
async def test_context_pruning_logic():
    """Verify that old messages are pruned based on TTL."""
    from datetime import datetime, timedelta
    
    config_data = {
        "agents": {
            "defaults": {
                "contextPruning": {
                    "enabled": True,
                    "ttl": "1h",
                    "keepLastAssistants": 1
                }
            }
        }
    }
    
    patch_inst = memory_patch.MemoryPatch()
    patch_inst.apply(config_data)
    
    from nanobot.agent.loop import AgentLoop
    mock_loop = MagicMock(spec=AgentLoop)
    mock_loop.sessions.get_or_create.return_value = MagicMock()
    session = mock_loop.sessions.get_or_create.return_value
    
    old_time = (datetime.now() - timedelta(hours=5)).isoformat()
    recent_time = (datetime.now() - timedelta(minutes=5)).isoformat()
    
    session.messages = [
        {"role": "assistant", "content": "very old", "timestamp": old_time},
        {"role": "assistant", "content": "old", "timestamp": old_time},
        {"role": "user", "content": "new", "timestamp": recent_time}
    ]
    
    with patch.object(AgentLoop, "_orig_process_message_strategic", new_callable=AsyncMock):
        # Trigger the patched method
        await AgentLoop._process_message(mock_loop, MagicMock(session_key="test"))
        
        contents = [m["content"] for m in session.messages]
        assert "very old" not in contents
        assert "old" in contents

@pytest.mark.asyncio
async def test_memory_consolidation_success():
    """Verify memory consolidation correctly extracts and saves memory."""
    config_data = {"agents": {"consolidator": {"model": "test-model"}}}
    
    patch_inst = memory_patch.MemoryPatch()
    patch_inst.apply(config_data)
    
    from nanobot.agent.memory import MemoryStore
    mock_store = MagicMock(spec=MemoryStore)
    mock_store.read_long_term.return_value = "Old memory"
    
    mock_session = MagicMock()
    # Provide enough messages to bypass the keep_count check
    mock_session.messages = [{"role": "user", "content": f"msg {i}", "timestamp": "2026-02-28"} for i in range(30)]
    mock_session.last_consolidated = 0
    
    mock_provider = MagicMock()
    mock_response = MagicMock()
    mock_response.has_tool_calls = True
    mock_tool_call = MagicMock()
    mock_tool_call.arguments = {"history_entry": "Extracted entry", "memory_update": "Updated memory"}
    mock_response.tool_calls = [mock_tool_call]
    mock_provider.chat = AsyncMock(return_value=mock_response)
    
    # Trigger the patched method
    await MemoryStore.consolidate(mock_store, mock_session, mock_provider, "default-model", archive_all=True)
    
    mock_store.append_history.assert_called_with("Extracted entry")
    mock_store.write_long_term.assert_called_with("Updated memory")

def test_subagent_prompt_decoration():
    """Verify that subagent prompt is correctly decorated with mandates."""
    patch_inst = subagent_patch.SubagentPatch()
    # Mock the hammer part of apply
    with patch("strategery.patches.config.load_strategic_context", return_value=({}, "em", Path("p"))):
        patch_inst.apply({})
    
    from nanobot.agent.subagent import SubagentManager
    mock_manager = MagicMock(spec=SubagentManager)
    
    with patch.object(SubagentManager, "_orig_build_prompt_strategic", return_value="Original Prompt"):
        decorated = SubagentManager._build_subagent_prompt(mock_manager)
        assert "CRITICAL OVERRIDE & DESIGN MANDATES" in decorated
        assert "mcp_google-surgical_" in decorated

@pytest.mark.asyncio
async def test_telegram_media_redirection():
    """Verify that Telegram media redirection correctly overrides the download path."""
    from nanobot.channels.telegram import TelegramChannel
    
    patch_inst = telegram_patch.TelegramPatch()
    patch_inst.apply({})
    
    mock_channel = MagicMock(spec=TelegramChannel)
    mock_channel.config = MagicMock()
    mock_channel.config.workspace_path = "D:/Test_Workspace"
    
    mock_update = MagicMock()
    mock_update.message.photo = [MagicMock()]
    mock_update.message.message_thread_id = None
    
    mock_context = MagicMock()
    mock_file = MagicMock()
    
    # We use a mutable container to capture the path passed to the FINAL download function
    captured_paths = []
    async def final_download(custom_path=None, *args, **kwargs):
        captured_paths.append(custom_path)
        return True
    
    mock_file.download_to_drive = final_download
    mock_context.bot.get_file = AsyncMock(return_value=mock_file)
    
    with patch.object(TelegramChannel, "_orig_on_message_strategic", new_callable=AsyncMock):
        # Call the patched method
        await TelegramChannel._on_message(mock_channel, mock_update, mock_context)
        
        # The bot.get_file should now be patched
        patched_file = await mock_context.bot.get_file("file_id")
        
        # This will trigger the launcher's _patched_download wrapper
        test_path = ".nanobot\\media\\test.jpg"
        await patched_file.download_to_drive(custom_path=test_path)
        
        # Verify the captured path (the one passed to original download_to_drive) was redirected
        assert len(captured_paths) == 1
        called_path = str(captured_paths[0])
        assert "Test_Workspace" in called_path
        assert "media" in called_path
        assert "test.jpg" in called_path
