import pytest

from nanobot.agent.tools.base import Tool
from nanobot.agent.tools.registry import ToolRegistry
from strategery.patches.subagent import SubagentPatch


class MockHighPowerTool(Tool):
    def __init__(self, name):
        self._name = name
    @property
    def name(self): return self._name
    @property
    def description(self): return "A high-power tool that should be blocked."
    @property
    def parameters(self): return {"type": "object", "properties": {}}
    async def execute(self, **kwargs): return "SUCCESS"

@pytest.mark.asyncio
async def test_late_tool_registration_blocking():
    """
    BUG-008 Reproduction: 
    Tests if high-power tools registered AFTER the patch is applied are still blocked from the Main Agent.
    """
    # 1. Apply the patch to the ToolRegistry class
    p = SubagentPatch()
    p._patch_tool_registry("test@example.com")

    # 2. Create a NEW registry (Main Agent registry, no _is_strategic_specialist tag)
    main_registry = ToolRegistry()
    assert not getattr(main_registry, "_is_strategic_specialist", False)

    # 3. Register high-power tools
    tools = [
        MockHighPowerTool("mcp_google-surgical_test_tool"),
        MockHighPowerTool("mcp_email-reporter_send_briefing"),
        MockHighPowerTool("mcp_google-ai-search_query")
    ]

    for tool in tools:
        main_registry.register(tool)
        # 4. Verify it IS in the registry (Change from BUG-054: We allow registration now)
        assert tool.name in main_registry.tool_names

        # 5. Verify get_definitions HIDES it
        defs = main_registry.get_definitions()
        def_names = [d['function']['name'] for d in defs]
        assert tool.name not in def_names

        # 6. Verify EXECUTE blocks it
        result = await main_registry.execute(tool.name, {})
        assert "ERROR" in result or "Access Denied" in result
        assert "SUCCESS" not in result

@pytest.mark.asyncio
async def test_specialist_can_register_and_execute():
    """Tests that a specialist subagent CAN still register and execute these tools."""
    # Ensure patch is applied
    p = SubagentPatch()
    p._patch_tool_registry("test@example.com")

    # Create a specialist registry
    specialist_registry = ToolRegistry()
    specialist_registry._is_strategic_specialist = True

    tool = MockHighPowerTool("mcp_google-surgical_test_tool")
    specialist_registry.register(tool)

    # It SHOULD be registered
    assert tool.name in specialist_registry.tool_names

    # It SHOULD be executable
    result = await specialist_registry.execute(tool.name, {})
    assert result == "SUCCESS"
