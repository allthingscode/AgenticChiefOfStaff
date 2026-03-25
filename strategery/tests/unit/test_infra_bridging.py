import pytest
from unittest.mock import AsyncMock, MagicMock
from strategery.patches.infra import strategic_bridge_mcp_sessions
from strategery.logic.infra_logic import strategic_mcp_logic

@pytest.mark.asyncio
async def test_strategic_bridge_mcp_sessions():
    """Verify that MCP sessions created by core are correctly bridged to the Strategic manager."""
    mcp_configs = {"test-server": MagicMock()}
    registry = MagicMock()
    stack = MagicMock()
    
    # Mock a tool in the registry that looks like an MCP tool
    mock_tool = MagicMock()
    mock_tool.name = "mcp_test-server_my-tool"
    mock_tool._session = MagicMock()
    mock_tool.description = "Test Description"
    mock_tool.parameters = {"type": "object"}
    # Use a real string for _original_name to avoid MagicMock comparison issues
    mock_tool._original_name = "my-tool"
    registry._tools = {"tool1": mock_tool}
    
    # Mock the original core connect function
    core_connect = AsyncMock(return_value={"test-server": "OK"})
    
    # Reset manager connections for a clean test
    strategic_mcp_logic._connections = {}
    
    # Create the bridged function
    bridged_func = strategic_bridge_mcp_sessions(None, None, None, core_connect)
    
    # Execute
    await bridged_func(mcp_configs, registry, stack)
    
    # VERIFY:
    # 1. Core function was called
    core_connect.assert_called_once_with(mcp_configs, registry, stack)
    
    # 2. Bridge detected the session and registered it in the Strategic manager
    assert "test-server" in strategic_mcp_logic._connections
    session, st, tools_def = strategic_mcp_logic._connections["test-server"]
    assert session == mock_tool._session
    assert st == stack
    assert len(tools_def) == 1
    assert tools_def[0].name == "my-tool"
