import pytest
import asyncio
import json
import uuid
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
from strategery.patches.subagent import SubagentPatch
from nanobot.agent.subagent import SubagentManager
from nanobot.agent.tools.spawn import SpawnTool
from nanobot.agent.tools.registry import ToolRegistry

@pytest.fixture
def mock_config():
    return {
        "agents": {
            "defaults": {
                "model": "default-model"
            },
            "specialists": {
                "researcher": {"model": "researcher-model"},
                "architect": {"model": "architect-model"}
            }
        },
        "strategic_edition": {
            "user_email": "test@example.com",
            "storage_root": "D:/Nanobot_Storage_Test"
        }
    }

@pytest.mark.asyncio
async def test_spawn_tool_parameter_injection(mock_config):
    """Verify that SpawnTool now accepts and passes the 'specialist' parameter."""
    with patch("strategery.patches.config.load_strategic_context", return_value=({}, "test@example.com", Path("D:/"))):
        patch_inst = SubagentPatch()
        patch_inst.apply(mock_config)
        
        mock_mgr = MagicMock(spec=SubagentManager)
        mock_mgr.spawn = AsyncMock(return_value="Subagent started")
        
        tool = SpawnTool(mock_mgr)
        
        # 1. Check Parameter Definition
        params = tool.parameters
        assert "specialist" in params["properties"]
        assert params["properties"]["specialist"]["enum"] == ["researcher", "architect"]
        
        # 2. Check Execution - Default specialist
        await tool.execute(task="test task")
        mock_mgr.spawn.assert_called_with(
            task="test task",
            label=None,
            origin_channel="cli",
            origin_chat_id="direct",
            session_key="cli:direct",
            specialist="researcher",
            host_tools=None
        )
        
        # 3. Check Execution - Explicit architect
        await tool.execute(task="arch task", specialist="architect")
        mock_mgr.spawn.assert_called_with(
            task="arch task",
            label=None,
            origin_channel="cli",
            origin_chat_id="direct",
            session_key="cli:direct",
            specialist="architect",
            host_tools=None
        )

@pytest.mark.asyncio
async def test_subagent_manager_model_selection(mock_config):
    """Verify that SubagentManager correctly selects the model based on the specialist parameter."""
    with patch("strategery.patches.config.load_strategic_context", return_value=({}, "test@example.com", Path("D:/"))):
        patch_inst = SubagentPatch()
        patch_inst.apply(mock_config)
        
        # Mock dependencies for SubagentManager
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock()
        mock_bus = MagicMock()
        
        mgr = SubagentManager(
            provider=mock_provider,
            workspace=Path("D:/test"),
            bus=mock_bus,
            model="fallback-model"
        )
        
        # We need to mock _run_subagent since we patched it, or just test the logic inside it
        # Actually, let's test the patched _run_subagent directly
        
        # 1. Test Researcher selection
        with patch.object(mgr, "_build_subagent_prompt", return_value="prompt"), \
             patch.object(mgr, "_announce_result", new_callable=AsyncMock):
            
            # Setup mock response to break the loop immediately
            mock_response = MagicMock()
            mock_response.has_tool_calls = False
            mock_response.content = "done"
            mock_provider.chat.return_value = mock_response
            
            await mgr._run_subagent("id1", "task1", "label1", {"channel": "c", "chat_id": "i"}, specialist="researcher")
            
            # Verify the model used in the chat call
            args, kwargs = mock_provider.chat.call_args
            assert kwargs["model"] == "researcher-model"

        # 2. Test Architect selection
        with patch.object(mgr, "_build_subagent_prompt", return_value="prompt"), \
             patch.object(mgr, "_announce_result", new_callable=AsyncMock):
            
            await mgr._run_subagent("id2", "task2", "label2", {"channel": "c", "chat_id": "i"}, specialist="architect")
            
            args, kwargs = mock_provider.chat.call_args
            assert kwargs["model"] == "architect-model"

        # 3. Test Fallback (Invalid Specialist)
        with patch.object(mgr, "_build_subagent_prompt", return_value="prompt"), \
             patch.object(mgr, "_announce_result", new_callable=AsyncMock):
            
            await mgr._run_subagent("id3", "task3", "label3", {"channel": "c", "chat_id": "i"}, specialist="invalid")
            
            args, kwargs = mock_provider.chat.call_args
            # Should fallback to researcher-model as per logic
            assert kwargs["model"] == "researcher-model"
