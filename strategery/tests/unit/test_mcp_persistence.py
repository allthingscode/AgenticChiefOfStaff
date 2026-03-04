import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from strategery.patches.infra import StrategicMcpManager

class AsyncContextManagerMock:
    def __init__(self, return_value):
        self.return_value = return_value
    async def __aenter__(self):
        return self.return_value
    async def __aexit__(self, exc_type, exc, tb):
        pass

@pytest.mark.asyncio
async def test_mcp_manager_persistence():
    """Verify that StrategicMcpManager reuses existing sessions."""
    manager = StrategicMcpManager()
    manager._connections = {}
    
    mock_registry = MagicMock()
    mock_registry.register = MagicMock()
    
    mcp_configs = {
        "test-server": MagicMock(command="test-cmd", args=[], env={}, tool_timeout=30)
    }
    
    # Mock return values for the context managers
    mock_stdio_returns = (AsyncMock(), AsyncMock()) # read, write
    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock()
    mock_session.list_tools = AsyncMock(return_value=MagicMock(tools=[MagicMock(name="test_tool")]))
    
    # We wrap them so they act like 'async with' targets
    with patch("mcp.client.stdio.stdio_client", return_value=AsyncContextManagerMock(mock_stdio_returns)) as mock_stdio_call, \
         patch("mcp.ClientSession", return_value=AsyncContextManagerMock(mock_session)) as mock_session_call, \
         patch("strategery.patches.infra.lifecycle_manager"):
        
        await manager.get_tools_for_subagent(mcp_configs, mock_registry, "subagent-1")
        assert "test-server" in manager._connections
        
        await manager.get_tools_for_subagent(mcp_configs, mock_registry, "subagent-2")
        
        # Should only have been called once due to persistence
        assert mock_stdio_call.call_count == 1
        assert mock_session_call.call_count == 1

@pytest.mark.asyncio
async def test_mcp_manager_error_isolation():
    """Verify that one failed MCP server doesn't block others."""
    manager = StrategicMcpManager()
    manager._connections = {}
    
    mock_registry = MagicMock()
    
    mcp_configs = {
        "fail-server": MagicMock(command="fail-cmd", args=[], env={}, tool_timeout=30),
        "ok-server": MagicMock(command="ok-cmd", args=[], env={}, tool_timeout=30)
    }
    
    def mock_stdio_side_effect(params):
        if params.command == "fail-cmd":
            raise Exception("Connection Failed")
        return AsyncContextManagerMock((AsyncMock(), AsyncMock()))

    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock()
    mock_session.list_tools = AsyncMock(return_value=MagicMock(tools=[MagicMock(name="ok_tool")]))

    with patch("mcp.client.stdio.stdio_client", side_effect=mock_stdio_side_effect), \
         patch("mcp.ClientSession", return_value=AsyncContextManagerMock(mock_session)), \
         patch("strategery.patches.infra.lifecycle_manager"):
        
        await manager.get_tools_for_subagent(mcp_configs, mock_registry, "subagent-1")
        
        assert "ok-server" in manager._connections
        assert "fail-server" not in manager._connections
