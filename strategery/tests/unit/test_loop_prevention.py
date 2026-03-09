import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from nanobot.agent.tools.registry import ToolRegistry
from strategery.patches.subagent import SubagentPatch

@pytest.fixture
def subagent_patch():
    return SubagentPatch()

@pytest.mark.asyncio
async def test_exec_polling_loop_prevention(subagent_patch):
    """Tests that repeated exec status calls are blocked."""
    subagent_patch._patch_tool_registry("test@example.com")
    
    registry = ToolRegistry()
    # Main Agent (no specialist tag)
    assert not getattr(registry, "_is_strategic_specialist", False)
    
    # Mock the original execute to return success
    with patch.object(ToolRegistry, "_orig_tool_execute_strategic", new_callable=AsyncMock) as mock_orig:
        mock_orig.return_value = "Success"
        
        # Use 'status' which is monitored for loops but NOT blocked as a bypass
        cmd_args = {"command": "status"}
        
        # 1-3. Success (Limit is 3)
        for i in range(3):
            res = await registry.execute("exec", cmd_args)
            assert res == "Success"
        
        # 4. Fourth Call -> LOOP DETECTED
        res4 = await registry.execute("exec", cmd_args)
        assert "Loop Detected" in res4
        assert "CRITICAL" in res4
        
        # Verify mock was only called 3 times
        assert mock_orig.call_count == 3

@pytest.mark.asyncio
async def test_specialist_blocked_after_five_calls(subagent_patch):
    """Tests that specialist subagents ARE blocked after 5 repeated exec status calls."""
    subagent_patch._patch_tool_registry("test@example.com")
    
    registry = ToolRegistry()
    registry._is_strategic_specialist = True
    
    with patch.object(ToolRegistry, "_orig_tool_execute_strategic", new_callable=AsyncMock) as mock_orig:
        mock_orig.return_value = "Success"
        cmd_args = {"command": "status"}
        
        # 1-5. Success (Limit is 5)
        for _ in range(5):
            res = await registry.execute("exec", cmd_args)
            assert res == "Success"
        
        # 6. LOOP DETECTED
        res6 = await registry.execute("exec", cmd_args)
        assert "Loop Detected" in res6
        assert mock_orig.call_count == 5

@pytest.mark.asyncio
async def test_exec_cli_bypass_blocking(subagent_patch):
    """Tests that attempts to call restricted tools via CLI are blocked."""
    subagent_patch._patch_tool_registry("test@example.com")
    registry = ToolRegistry()
    
    # 1. Block Google Surgical via CLI
    cmd_args = {"command": "python -m nanobot mcp google-surgical list_calendars"}
    res = await registry.execute("exec", cmd_args)
    assert "Access Denied" in res
    assert "CLI bypass" in res
    
    # 2. Block AI Search via CLI
    cmd_args2 = {"command": "python -m nanobot mcp google-ai-search search_ai --query test"}
    res2 = await registry.execute("exec", cmd_args2)
    assert "Access Denied" in res2
    
    # 3. Block Status via CLI (Directly or via module)
    cmd_args3 = {"command": "python -m nanobot status"}
    res3 = await registry.execute("exec", cmd_args3)
    assert "Access Denied" in res3

@pytest.mark.asyncio
async def test_spawn_termination_directive(subagent_patch):
    """Tests that 'spawn' returns a termination mandate for the Main Agent."""
    subagent_patch._patch_tool_registry("test@example.com")
    registry = ToolRegistry()
    
    with patch.object(ToolRegistry, "_orig_tool_execute_strategic", new_callable=AsyncMock) as mock_orig:
        mock_orig.return_value = "Subagent spawned (id: 123)."
        
        res = await registry.execute("spawn", {"task": "test"})
        assert "123" in res
        assert "STRATEGIC MANDATE: STOP Turn" in res

@pytest.mark.asyncio
async def test_history_md_bypass_blocking(subagent_patch):
    """Tests that attempts to poll HISTORY.md via 'exec' are blocked."""
    subagent_patch._patch_tool_registry("test@example.com")
    registry = ToolRegistry()
    
    # 1. Block findstr on HISTORY.md
    cmd_args = {"command": "findstr /C:\"System Health Check\" D:\\Nanobot_Storage\\workspace\\memory\\HISTORY.md"}
    res = await registry.execute("exec", cmd_args)
    assert "Access Denied" in res
    assert "HISTORY.md is RETIRED" in res
    
    # 2. Block direct grep/cat on history
    cmd_args2 = {"command": "cat history.md"}
    res2 = await registry.execute("exec", cmd_args2)
    assert "Access Denied" in res2
