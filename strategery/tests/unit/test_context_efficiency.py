import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from nanobot.agent.tools.filesystem import ReadFileTool
from strategery.patches.subagent import SubagentPatch

@pytest.fixture
def subagent_patch():
    return SubagentPatch()

@pytest.mark.asyncio
async def test_read_file_efficiency_enforcement(subagent_patch, tmp_path):
    """Verify that specialists are blocked from reading large files (BUG-164)."""
    subagent_patch._patch_read_file_tool()
    
    # Create a "large" file (15KB)
    large_file = tmp_path / "large_log.txt"
    large_file.write_text("A" * 15 * 1024)
    
    # Create a "small" file (5KB)
    small_file = tmp_path / "small_config.json"
    small_file.write_text("B" * 5 * 1024)
    
    # 1. Specialist Case -> Large File Blocked
    mock_registry_specialist = MagicMock()
    mock_registry_specialist._is_strategic_specialist = True
    
    tool = ReadFileTool()
    tool._registry = mock_registry_specialist
    
    # Mock original execute to avoid actual file system read in test if needed, 
    # but here we want to see the patch logic.
    with patch.object(ReadFileTool, "_orig_execute_strategic", new_callable=AsyncMock) as mock_orig:
        mock_orig.return_value = "Content"
        
        # Test Large File
        res = await tool.execute(path=str(large_file))
        assert "is too large" in res
        assert "Specialist Mandate (BUG-164)" in res
        mock_orig.assert_not_called()
        
        # Test Small File
        res_small = await tool.execute(path=str(small_file))
        assert res_small == "Content"
        mock_orig.assert_called_once_with(str(small_file))

    # 2. Main Agent Case -> Large File Allowed
    mock_registry_main = MagicMock()
    mock_registry_main._is_strategic_specialist = False
    
    tool_main = ReadFileTool()
    tool_main._registry = mock_registry_main
    
    with patch.object(ReadFileTool, "_orig_execute_strategic", new_callable=AsyncMock) as mock_orig_main:
        mock_orig_main.return_value = "Large Content"
        
        res = await tool_main.execute(path=str(large_file))
        assert res == "Large Content"
        mock_orig_main.assert_called_once_with(str(large_file))
