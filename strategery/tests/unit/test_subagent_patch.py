from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
    mock_tool.to_schema.return_value = {"type": "function", "function": {"name": "mcp_google-surgical_list_tasks"}}

    registry = ToolRegistry()
    # Ensure it's not tagged as a specialist
    assert not getattr(registry, "_is_strategic_specialist", False)

    # 1. Test Registration Allowed (BUG-054 Bridging Requirement)
    registry.register(mock_tool)
    assert "mcp_google-surgical_list_tasks" in registry.tool_names

    # 2. Test Definition Hiding (Prompt level)
    defs = registry.get_definitions()
    tool_names_in_defs = [d.get("function", {}).get("name") for d in defs]
    assert "mcp_google-surgical_list_tasks" not in tool_names_in_defs

    # 3. Test Execution Block (Hard Block)
    result = await registry.execute("mcp_google-surgical_list_tasks", {})
    assert "is restricted for your role" in result
    assert "Main Agent" in result

@pytest.mark.asyncio
async def test_tool_registry_circuit_breaker(subagent_patch, mock_tool):
    # Apply patch
    subagent_patch._patch_tool_registry("test@example.com")

    registry = ToolRegistry()
    # Manually inject to bypass registration check
    registry._tools["mcp_google-surgical_list_tasks"] = mock_tool

    # 1. First Attempt -> Normal Block
    result = await registry.execute("mcp_google-surgical_list_tasks", {})
    assert "is restricted for your role" in result

    # 2. Second Attempt -> Circuit Breaker (Hard Lock)
    # Mandate (BUG-169): Circuit breaker triggers after 2 identical attempts for Main Agent
    result = await registry.execute("mcp_google-surgical_list_tasks", {})
    assert "CRITICAL: Tool Loop Detected!" in result
    assert "You have attempted to call 'mcp_google-surgical_list_tasks' with the EXACT same arguments" in result

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
    # Mandate (BUG-171): Mock the correct patched name
    with patch.object(ToolRegistry, "_orig_execute_strategic", new_callable=AsyncMock) as mock_orig:
        mock_orig.return_value = "success"
        result = await registry.execute("mcp_google-surgical_list_tasks", {})
        assert result == "success"
        mock_orig.assert_called_once()

@pytest.mark.asyncio
async def test_web_search_deprecation(subagent_patch):
    subagent_patch._patch_tool_registry("test@example.com")
    registry = ToolRegistry()

    result = await registry.execute("web_search", {"query": "test"})
    assert "is restricted for your role" in result

@pytest.mark.asyncio
async def test_subagent_prompt_patch(subagent_patch):
    """Verify that _build_subagent_prompt is patched with specialist instructions."""
    from pathlib import Path

    from nanobot.agent.subagent import SubagentManager

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
    manager._orig_build_subagent_prompt_strategic = MagicMock(return_value="Base.")

    # Call patched prompt
    prompt = manager._build_subagent_prompt()

    assert "## 🛡️ STRATEGIC SPECIALIST INSTRUCTIONS" in prompt
    assert "mcp_google-ai-search_search_ai" in prompt

@pytest.mark.asyncio
async def test_tool_registry_telemetry_logging(subagent_patch):
    """Verify telemetry logging during definition retrieval."""
    subagent_patch._patch_tool_registry("test@example.com")
    registry = ToolRegistry()

    with patch("strategery.patches.subagent.strategic_logger") as mock_logger:
        registry.get_definitions()
        assert mock_logger.info.call_count >= 1

        # Check for new log format
        log_msg = mock_logger.info.call_args_list[0][0][0]
        assert "Initialized definitions" in log_msg
