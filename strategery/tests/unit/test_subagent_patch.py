import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from nanobot.agent.tools.registry import ToolRegistry
from strategery.patches.subagent import SubagentPatch

@pytest.fixture
def subagent_patch():
    return SubagentPatch()

@pytest.fixture
def mock_tool():
    tool = MagicMock()
    tool.name = "mcp_google-surgical_list_tasks"
    return tool

@pytest.mark.asyncio
async def test_tool_registry_blocks_high_power_for_main_agent(subagent_patch, mock_tool):
    # Apply patch
    subagent_patch._patch_tool_registry("test@example.com")
    
    registry = ToolRegistry()
    # Ensure it's not tagged as a specialist
    assert not getattr(registry, "_is_strategic_specialist", False)
    
    # 1. Test Registration Block
    registry.register(mock_tool)
    assert "mcp_google-surgical_list_tasks" not in registry.tool_names
    
    # 2. Test Execution Block (Hard Block)
    # Manually inject to bypass registration check for the sake of testing the execution block
    registry._tools["mcp_google-surgical_list_tasks"] = mock_tool
    
    result = await registry.execute("mcp_google-surgical_list_tasks", {})
    assert "restricted to SPECIALIST subagents" in result
    assert "MUST use 'spawn' to delegate this task" in result
@pytest.mark.asyncio
async def test_tool_registry_circuit_breaker(subagent_patch, mock_tool):
    # Apply patch
    subagent_patch._patch_tool_registry("test@example.com")
    
    registry = ToolRegistry()
    # Manually inject to bypass registration check
    registry._tools["mcp_google-surgical_list_tasks"] = mock_tool
    
    # 1. First Attempt -> Normal Block
    result = await registry.execute("mcp_google-surgical_list_tasks", {})
    assert "restricted to SPECIALIST subagents" in result
    
    # 2. Second Attempt -> Circuit Breaker (Hard Lock)
    result = await registry.execute("mcp_google-surgical_list_tasks", {})
    assert "CRITICAL ERROR" in result
    assert "HARD-LOCKED" in result
    assert "You MUST STOP trying to call this tool directly" in result

@pytest.mark.asyncio
async def test_tool_registry_allows_high_power_for_specialist(subagent_patch, mock_tool):
    # Apply patch
    subagent_patch._patch_tool_registry("test@example.com")
    
    registry = ToolRegistry()
    registry._is_strategic_specialist = True
    
    # 1. Test Registration Allowed
    registry.register(mock_tool)
    assert "mcp_google-surgical_list_tasks" in registry.tool_names
    
    # 2. Test Execution Allowed (calls original)
    with patch.object(ToolRegistry, "_orig_tool_execute_strategic", new_callable=AsyncMock) as mock_orig:
        mock_orig.return_value = "success"
        result = await registry.execute("mcp_google-surgical_list_tasks", {})
        assert result == "success"
        mock_orig.assert_called_once()

@pytest.mark.asyncio
async def test_web_search_deprecation(subagent_patch):
    subagent_patch._patch_tool_registry("test@example.com")
    registry = ToolRegistry()
    
    result = await registry.execute("web_search", {"query": "test"})
    assert "restricted to SPECIALIST" in result
    assert "mcp_google-ai-search_search_ai" in result

@pytest.mark.asyncio
async def test_subagent_prompt_patch(subagent_patch):
    """Verify that _build_subagent_prompt is patched with specialist instructions."""
    from nanobot.agent.subagent import SubagentManager
    from pathlib import Path
    
    # Apply patch
    if hasattr(SubagentManager, "_orig_build_subagent_prompt_strategic"):
        SubagentManager._build_subagent_prompt = SubagentManager._orig_build_subagent_prompt_strategic
        del SubagentManager._orig_build_subagent_prompt_strategic
        
    subagent_patch._patch_subagent_manager({})
    
    # Mock dependencies for SubagentManager init
    mock_bus = MagicMock()
    mock_provider = MagicMock()
    mock_provider.get_default_model.return_value = "gpt-4"
    
    manager = SubagentManager(provider=mock_provider, workspace=Path("/tmp"), bus=mock_bus)
    
    # Call patched prompt
    prompt = manager._build_subagent_prompt()
    
    assert "## 🛡️ STRATEGIC SPECIALIST INSTRUCTIONS" in prompt
    assert "mcp_google-ai-search_search_ai" in prompt
    assert "NETWORK DIAGNOSTICS" in prompt
    assert "Do NOT use 'ping'" in prompt
