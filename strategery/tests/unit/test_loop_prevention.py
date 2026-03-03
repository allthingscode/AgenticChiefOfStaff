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
        
        cmd_args = {"command": "ping 8.8.8.8"}
        
        # 1. First Call -> Success
        res1 = await registry.execute("exec", cmd_args)
        assert res1 == "Success"
        
        # 2. Second Call -> Success
        res2 = await registry.execute("exec", cmd_args)
        assert res2 == "Success"
        
        # 3. Third Call -> LOOP DETECTED
        res3 = await registry.execute("exec", cmd_args)
        assert "Loop Detected" in res3
        assert "CRITICAL ERROR" in res3
        
        # Verify mock was only called twice
        assert mock_orig.call_count == 2

@pytest.mark.asyncio
async def test_specialist_not_blocked_from_polling(subagent_patch):
    """Tests that specialist subagents are NOT blocked from repeated exec (though they shouldn't do it)."""
    subagent_patch._patch_tool_registry("test@example.com")
    
    registry = ToolRegistry()
    registry._is_strategic_specialist = True
    
    with patch.object(ToolRegistry, "_orig_tool_execute_strategic", new_callable=AsyncMock) as mock_orig:
        mock_orig.return_value = "Success"
        cmd_args = {"command": "status"}
        
        await registry.execute("exec", cmd_args)
        await registry.execute("exec", cmd_args)
        res3 = await registry.execute("exec", cmd_args)
        
        assert res3 == "Success"
        assert mock_orig.call_count == 3

@pytest.mark.asyncio
async def test_exec_cli_bypass_blocking(subagent_patch):
    """Tests that attempts to call restricted tools via CLI are blocked."""
    subagent_patch._patch_tool_registry("test@example.com")
    registry = ToolRegistry()
    
    # 1. Block Google Surgical via CLI
    cmd_args = {"command": "python -m nanobot mcp google-surgical list_calendars"}
    res = await registry.execute("exec", cmd_args)
    assert "Access Denied" in res
    assert "CLI bypass" in res or "Strategic Mandates" in res
    
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
        mock_orig.return_value = "Subagent [123] spawned."
        
        res = await registry.execute("spawn", {"task": "test"})
        assert "Subagent [123] spawned." in res
        assert "STRATEGIC MANDATE: STOP Turn" in res
        assert "Your turn is now OVER" in res

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

    # 3. Block type on history
    cmd_args3 = {"command": "type D:\\Nanobot_Storage\\workspace\\memory\\history.md"}
    res3 = await registry.execute("exec", cmd_args3)
    assert "Access Denied" in res3

    # 4. Block tail on history
    cmd_args4 = {"command": "tail -n 5 history.md"}
    res4 = await registry.execute("exec", cmd_args4)
    assert "Access Denied" in res4

    # 5. Block PowerShell Get-Content on history
    cmd_args5 = {"command": "powershell -command \"Get-Content history.md -Tail 5\""}
    res5 = await registry.execute("exec", cmd_args5)
    assert "Access Denied" in res5
