import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from nanobot.agent.subagent import SubagentManager
from nanobot.agent.tools.registry import ToolRegistry
from strategery.patches.subagent import SubagentPatch

@pytest.fixture
def mock_specialist_config():
    return {
        "agents": {
            "specialists": {
                "architect": {
                    "keywords": ["architect", "design", "refactor"],
                    "model": "special-architect-model"
                },
                "researcher": {
                    "keywords": ["research", "search", "verify"],
                    "model": "special-research-model"
                }
            }
        }
    }

@pytest.mark.asyncio
async def test_subagent_manager_integrated_routing(mock_context):
    """
    Integrated test to verify that SubagentManager temporarily switches models
    and uses the StrategicSubagentRegistry during execution.
    """
    # Override default context config for this test
    mock_context.config = {
        "agents": {
            "specialists": {
                "architect": {"model": "special-architect-model"},
                "researcher": {"model": "special-research-model"}
            }
        }
    }

    # 1. Apply the patch
    patch_inst = SubagentPatch()

    # Forcibly reset existing patches to allow re-patching with mock config
    if hasattr(SubagentManager, "_orig_run_subagent_strategic"):
        delattr(SubagentManager, "_orig_run_subagent_strategic")
    if hasattr(SubagentManager, "_orig_announce_result_strategic"):
        delattr(SubagentManager, "_orig_announce_result_strategic")

    # We also need to mock ToolRegistry.register to avoid loading real tools
    with patch.object(ToolRegistry, "register"):
        patch_inst.apply(mock_context)

    # 2. Setup mock SubagentManager
    mock_mgr = MagicMock(spec=SubagentManager)
    mock_mgr.model = "default-model"
    mock_mgr.bus = MagicMock()
    mock_mgr.workspace = "test-workspace"
    mock_mgr.restrict_to_workspace = False
    mock_mgr.exec_config = MagicMock()
    mock_mgr.exec_config.timeout = 30
    mock_mgr.exec_config.path_append = []
    mock_mgr.brave_api_key = None
    mock_mgr.web_proxy = None
    mock_mgr.provider = MagicMock()
    mock_mgr.temperature = 0.7
    mock_mgr.max_tokens = 4096
    mock_mgr.reasoning_effort = None
    
    # Mock the chat method to avoid real LLM calls
    mock_mgr.provider.chat = AsyncMock()
    mock_mgr.provider.chat.return_value = MagicMock(has_tool_calls=False, content="Done")

    # 3. Execute Researcher Task
    await SubagentManager._run_subagent(mock_mgr, "task-1", "research the history", "Researcher", {"channel": "test", "chat_id": "123"})

    # 4. Verify Researcher Routing
    # Check that chat was called with the special model
    args, kwargs = mock_mgr.provider.chat.call_args
    assert kwargs["model"] == "special-research-model"

@pytest.mark.asyncio
async def test_architect_routing_uses_pro_model(mock_context):
    """Verify that the Architect specialist correctly uses the 'pro' model from config (BUG-056)."""
    from nanobot.agent.subagent import SubagentManager
    from nanobot.agent.tools.registry import ToolRegistry
    
    mock_context.config = {
        "agents": {
            "specialists": {
                "architect": {"model": "special-architect-model"},
                "researcher": {"model": "special-research-model"}
            }
        }
    }

    # Setup mock SubagentManager
    mock_mgr = MagicMock(spec=SubagentManager)
    mock_mgr.model = "default-model"
    mock_mgr.provider = MagicMock()
    mock_mgr.provider.chat = AsyncMock()
    mock_mgr.provider.chat.return_value = MagicMock(has_tool_calls=False, content="Done")
    mock_mgr.bus = MagicMock()
    mock_mgr.workspace = "test-workspace"
    mock_mgr.restrict_to_workspace = False
    mock_mgr.exec_config = MagicMock()
    mock_mgr.exec_config.timeout = 30
    mock_mgr.exec_config.path_append = []
    mock_mgr.web_proxy = None
    mock_mgr.temperature = 0.7
    mock_mgr.max_tokens = 4096
    mock_mgr.reasoning_effort = None
    
    # Execute Architect Task (specialist="architect")
    with patch.object(ToolRegistry, "register"):
        SubagentPatch().apply(mock_context)
        
        await SubagentManager._run_subagent(
            mock_mgr, "task-2", "design system", "Architect", {"channel": "test", "chat_id": "123"}, 
            specialist="architect"
        )

    # Verify Architect Routing
    args, kwargs = mock_mgr.provider.chat.call_args
    assert kwargs["model"] == "special-architect-model"

@pytest.mark.asyncio
async def test_subagent_registry_tool_access(mock_context):
    """Verify that high-power tools are ALLOWED for specialists but BLOCKED for others."""
    SubagentPatch().apply(mock_context)

    from nanobot.agent.tools.registry import ToolRegistry

    # 1. Main Agent Registry (Not tagged)
    main_reg = ToolRegistry()
    assert getattr(main_reg, "_is_strategic_specialist", False) is False

    mock_tool = MagicMock()
    mock_tool.name = "mcp_google-surgical_search"
    mock_tool.to_schema.return_value = {"type": "function", "function": {"name": "mcp_google-surgical_search"}}

    # Should be registered (for bridging) but hidden from definitions
    main_reg.register(mock_tool)
    assert "mcp_google-surgical_search" in main_reg.tool_names
    
    defs = main_reg.get_definitions()
    assert "mcp_google-surgical_search" not in [d.get("function", {}).get("name") for d in defs]

    # 2. Specialist Registry (Tagged)
    spec_reg = ToolRegistry()
    spec_reg._is_strategic_specialist = True
    
    spec_reg.register(mock_tool)
    assert "mcp_google-surgical_search" in spec_reg.tool_names
    
    spec_defs = spec_reg.get_definitions()
    assert "mcp_google-surgical_search" in [d.get("function", {}).get("name") for d in spec_defs]
