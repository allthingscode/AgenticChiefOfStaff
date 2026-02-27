import asyncio
import sys
import pytest
from nanobot.agent.tools.shell import ExecTool

@pytest.mark.asyncio
async def test_exec_date_timeout():
    # This test might fail/timeout if it truly hangs.
    # We'll set a short timeout for the tool itself.
    tool = ExecTool(timeout=5)
    
    # On Windows, 'date' is interactive in cmd.exe, but we now rewrite it to 'date /t'
    if sys.platform == "win32":
        result = await tool.execute(command="date")
        print(f"\nResult of 'date': {result}")
        # It should NOT timeout anymore
        assert "Error: Command timed out" not in result
        assert len(result.strip()) > 0
    else:
        result = await tool.execute(command="date")
        print(f"\nResult of 'date': {result}")
        assert "2026" in result or "2025" in result # adjust for year if needed

@pytest.mark.asyncio
async def test_exec_time_fixed():
    tool = ExecTool(timeout=5)
    if sys.platform == "win32":
        # 'time' is also interactive in cmd.exe
        result = await tool.execute(command="time")
        print(f"\nResult of 'time': {result}")
        assert "Error: Command timed out" not in result
        assert len(result.strip()) > 0
    else:
        # On POSIX 'time' might behave differently (measure command execution)
        # but the tool handles it fine or it's not a hang culprit.
        pass

@pytest.mark.asyncio
async def test_exec_date_fixed():
    tool = ExecTool(timeout=5)
    if sys.platform == "win32":
        # Using date /t should work and NOT timeout
        result = await tool.execute(command="date /t")
        print(f"\nResult of 'date /t': {result}")
        assert "Error: Command timed out" not in result
        assert len(result.strip()) > 0
    else:
        result = await tool.execute(command="date")
        print(f"\nResult of 'date': {result}")
        assert len(result.strip()) > 0
