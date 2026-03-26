from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanobot.agent.subagent import SubagentManager
from nanobot.agent.tools.spawn import SpawnTool
from strategery.patches.subagent import SubagentPatch


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
async def test_spawn_tool_parameter_injection(mock_context):
    """Verify that SpawnTool now accepts and passes the 'specialist' parameter."""
    patch_inst = SubagentPatch()
    patch_inst.apply(mock_context)

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
        host_tools=None,
        attachments=None
    )
@pytest.mark.asyncio
async def test_subagent_manager_model_selection(mock_context):
    """Verify that SubagentManager correctly selects the model based on the specialist parameter."""
    # Setup specific model config in context via typed access
    mock_context.config.agents.specialists = {
        "researcher": {"model": "researcher-model"},
        "architect": {"model": "architect-model"}
    }

    patch_inst = SubagentPatch()
    patch_inst.apply(mock_context)

    # Mock dependencies for SubagentManager
    mock_provider = MagicMock()
    mock_provider.chat = AsyncMock()
    mock_bus = MagicMock()

    mgr = SubagentManager(
        provider=mock_provider,
        workspace=mock_context.workspace_root,
        bus=mock_bus,
        model="fallback-model"
    )

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
