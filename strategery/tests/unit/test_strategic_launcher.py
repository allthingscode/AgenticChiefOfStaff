import pytest
from unittest.mock import patch, MagicMock, AsyncMock
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
        # Call it with: self, bus, original-model
        launcher._patched_hb_init(mock_self, "bus", "original-model")
        
        # In _patched_hb_init(self, *args, **kwargs):
        #   args = ("bus", "original-model")
        #   len(args) == 2. So it replaces args[1] with "fast-model-override"
        #   Then it calls _orig_hb_init(self, *args, **kwargs)
        
        args, _ = mock_orig_init.call_args
        # args[0] is mock_self (passed as positional self)
        # args[1] is "bus"
        # args[2] is "fast-model-override"
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
    
    # 1. Very old message
    old_time = (datetime.now() - timedelta(hours=5)).isoformat()
    # 2. Recent message
    recent_time = (datetime.now() - timedelta(minutes=5)).isoformat()
    
    session.messages = [
        {"role": "user", "content": "old", "timestamp": old_time},
        {"role": "assistant", "content": "old response", "timestamp": old_time},
        {"role": "user", "content": "new", "timestamp": recent_time}
    ]
    
    with patch.object(launcher, "_orig_process_message", new_callable=AsyncMock) as mock_orig:
        await launcher._patched_process_message(mock_loop, MagicMock(), session_key="test")
        
        # Verify old assistant message was pruned, but user messages are kept or 
        # based on keepLastAssistants logic.
        # In the patch: "if not is_old or assistant_count <= keepLastAssistants or role == 'user': new_msgs.append(m)"
        # So 'old' (user) is kept. 'old response' (assistant) is kept if assistant_count (1) <= 1. 
        # Since it's the first assistant message from the end, it should be kept.
        
        # Let's test with 2 old assistant messages and keepLastAssistants=1
        session.messages = [
            {"role": "assistant", "content": "very old", "timestamp": old_time},
            {"role": "assistant", "content": "old", "timestamp": old_time},
            {"role": "user", "content": "new", "timestamp": recent_time}
        ]
        await launcher._patched_process_message(mock_loop, MagicMock(), session_key="test")
        
        # The 'very old' assistant message should be pruned.
        roles = [m["content"] for m in session.messages]
        assert "very old" not in roles
        assert "old" in roles
