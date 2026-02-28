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

# Import the launcher and relevant nanobot modules
import strategery.strategic_launcher as launcher
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
    """Verify that _patched_migrate correctly strips custom keys."""
    # We use the already-patched function from the launcher
    data = launcher._patched_migrate(mock_config_data.copy())
    
    # Verify custom keys are stripped
    assert "strategic_edition" not in data
    assert "memory" not in data
    assert "compaction" not in data["agents"]["defaults"]
    assert "contextPruning" not in data["agents"]["defaults"]
    assert "keywords" not in data["agents"]["specialists"]["researcher"]
    
    # Verify RAW_CONFIG was captured
    assert launcher.RAW_CONFIG["strategic_edition"]["user_email"] == "test@example.com"

@pytest.mark.asyncio
async def test_litellm_logging_patch():
    """Verify LiteLLMProvider.chat is patched to log the request."""
    from nanobot.providers.litellm_provider import LiteLLMProvider
    
    mock_self = MagicMock(spec=LiteLLMProvider)
    mock_self.default_model = "test-model"
    mock_self.api_key = "test-key"
    mock_self._resolve_model.return_value = "test-model"
    mock_self._supports_cache_control.return_value = False
    
    # Mock the original chat method (which is stored in launcher._orig_litellm_chat)
    with patch.object(launcher, "_orig_litellm_chat", new_callable=AsyncMock) as mock_orig:
        from loguru import logger
        with patch.object(logger, "info") as mock_logger:
            await launcher._patched_litellm_chat(mock_self, messages=[{"role": "user", "content": "hi"}])
            
            mock_logger.assert_called_with("[Logging Patch] LiteLLM request: model={}", "test-model")
            mock_orig.assert_called_once()

def test_heartbeat_init_patch():
    """Verify HeartbeatService model is overridden from config."""
    launcher.RAW_CONFIG = {
        "agents": {
            "heartbeat": {"model": "fast-model-override"}
        }
    }
    
    mock_orig_init = MagicMock()
    with patch.object(launcher, "_orig_hb_init", mock_orig_init):
        mock_self = MagicMock()
        launcher._patched_hb_init(mock_self, "bus", "original-model")
        
        args, _ = mock_orig_init.call_args
        assert args[2] == "fast-model-override"

@pytest.mark.asyncio
async def test_google_hammer_mcp_patch():
    """Verify ToolRegistry.execute forces the user email for google-surgical tools."""
    launcher.USER_EMAIL = "forced@example.com"
    
    with patch.object(launcher, "_orig_tool_execute", new_callable=AsyncMock) as mock_orig:
        args = {"user_google_email": "someone@else.com", "other": "param"}
        mock_registry = MagicMock()
        await launcher._patched_tool_execute(mock_registry, "mcp_google-surgical_create_task", args)
        
        mock_orig.assert_called_once()
        c_args, _ = mock_orig.call_args
        assert c_args[2]["user_google_email"] == "forced@example.com"

@pytest.mark.asyncio
async def test_specialist_routing_logic():
    """Verify that the specialist model is correctly selected based on keywords."""
    launcher.RAW_CONFIG = {
        "agents": {
            "specialists": {
                "researcher": {"model": "powerful-model", "keywords": ["find", "search"]},
                "architect": {"model": "design-model", "keywords": ["design"]}
            }
        }
    }
    
    mock_manager = MagicMock()
    mock_manager.model = "default-model"
    
    captured_model = []
    async def mock_run(self, task_id, task, label, origin):
        captured_model.append(self.model)
        return "ok"

    with patch.object(launcher, "_orig_run_subagent", mock_run):
        await launcher._patched_run_subagent(mock_manager, "id", "find the documents", "label", "origin")
        
        assert "powerful-model" in captured_model
        assert mock_manager.model == "default-model"

@pytest.mark.asyncio
async def test_context_pruning_logic():
    """Verify that old messages are pruned based on TTL."""
    from datetime import datetime, timedelta
    
    launcher.RAW_CONFIG = {
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
    
    mock_loop = MagicMock()
    mock_loop.sessions.get_or_create.return_value = MagicMock()
    session = mock_loop.sessions.get_or_create.return_value
    
    old_time = (datetime.now() - timedelta(hours=5)).isoformat()
    recent_time = (datetime.now() - timedelta(minutes=5)).isoformat()
    
    session.messages = [
        {"role": "assistant", "content": "very old", "timestamp": old_time},
        {"role": "assistant", "content": "old", "timestamp": old_time},
        {"role": "user", "content": "new", "timestamp": recent_time}
    ]
    
    with patch.object(launcher, "_orig_process_message", new_callable=AsyncMock) as mock_orig:
        await launcher._patched_process_message(mock_loop, MagicMock(), session_key="test")
        
        roles = [m["content"] for m in session.messages]
        assert "very old" not in roles
        assert "old" in roles

@pytest.mark.asyncio
async def test_memory_consolidation_success():
    """Verify memory consolidation correctly extracts and saves memory."""
    launcher.RAW_CONFIG = {"agents": {"consolidator": {"model": "test-model"}}}
    
    mock_store = MagicMock()
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
    
    await launcher._patched_consolidate(mock_store, mock_session, mock_provider, "default-model", archive_all=True)
    
    mock_store.append_history.assert_called_with("Extracted entry")
    mock_store.write_long_term.assert_called_with("Updated memory")

@pytest.mark.asyncio
async def test_memory_consolidation_regex_recovery():
    """Verify regex recovery when tool call fails."""
    launcher.RAW_CONFIG = {"agents": {"consolidator": {"model": "test-model"}}}
    
    mock_store = MagicMock()
    mock_store.read_long_term.return_value = "Old memory"
    
    mock_session = MagicMock()
    mock_session.messages = [{"role": "user", "content": "Hello"}]
    mock_session.last_consolidated = 0
    
    mock_provider = MagicMock()
    mock_response = MagicMock()
    mock_response.has_tool_calls = False
    mock_response.content = 'Here is the JSON: {"history_entry": "Regex Entry", "memory_update": "Regex Memory"}'
    mock_provider.chat = AsyncMock(return_value=mock_response)
    
    await launcher._patched_consolidate(mock_store, mock_session, mock_provider, "test-model", archive_all=True)
    
    mock_store.append_history.assert_called_with("Regex Entry")
    mock_store.write_long_term.assert_called_with("Regex Memory")

def test_subagent_prompt_decoration():
    """Verify that subagent prompt is correctly decorated with mandates."""
    mock_manager = MagicMock()
    with patch.object(launcher, "_orig_build_prompt", return_value="Original Prompt"):
        decorated = launcher._patched_build_prompt(mock_manager)
        assert "CRITICAL OVERRIDE & DESIGN MANDATES" in decorated
        assert "mcp_google-surgical_" in decorated

@pytest.mark.asyncio
async def test_telegram_media_redirection():
    """Verify that Telegram media redirection correctly overrides the download path."""
    from nanobot.channels.telegram import TelegramChannel
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
    
    with patch.object(launcher, "_orig_on_message", new_callable=AsyncMock):
        await launcher._patched_on_message(mock_channel, mock_update, mock_context)
        
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
