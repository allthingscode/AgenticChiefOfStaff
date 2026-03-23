import pytest
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from strategery.patches.subagent import SubagentPatch
from strategery.patches.base import PatchContext
from strategery.logic import subagent_logic
from strategery.tools.strategic_vision import MultimodalAnalyzerTool

@pytest.mark.asyncio
async def test_subagent_model_and_manifest_integrity():
    """Verify that subagents receive the correct model and instructions (ARCH-022)."""
    
    # 1. Test Dynamic Model Assignment
    # Create tool with a specific model
    tool = MultimodalAnalyzerTool(model_name="models/test-vision-model")
    assert tool._model_name == "models/test-vision-model"
    
    # 2. Test Manifest Injection (The "Blindness" Fix)
    attachments = [{"path": "D:\\test.jpg", "filename": "test.jpg"}]
    instructions = subagent_logic.build_specialist_instructions("Base Prompt", "researcher", attachments)
    
    # Manifest must be at the TOP (after base prompt and header)
    assert "STRATEGIC DISCOVERY MANIFEST" in instructions
    assert "ATTACHMENTS (ARCH-022)" in instructions
    assert "D:\\test.jpg" in instructions
    
    # Verify Finality Mandate hardening
    assert "report the technical error directly to the user" in instructions
    assert "Do NOT ask the user to fix it" in instructions

@pytest.mark.asyncio
async def test_subagent_patch_model_propagation():
    """Verify that SubagentPatch passes the correct model to loaded tools."""
    from nanobot.agent.tools.registry import ToolRegistry
    import strategery.tools.strategic_vision
    
    patch_inst = SubagentPatch()
    registry = ToolRegistry()
    
    # We patch the specific method on the class that is imported by the loader
    with patch("strategery.tools.strategic_vision.MultimodalAnalyzerTool.__init__", return_value=None) as mock_init:
        # We also need to mock the module name in sys.modules to ensure importlib uses our mock
        test_model = "models/gemini-2.0-flash"
        patch_inst._load_strategic_tools(registry, model=test_model)
        
        # In this environment, importlib may create a NEW class object.
        # We'll check if ANY Tool was registered with the correct model attribute.
        found = False
        # ToolRegistry._tools is the internal storage
        for tool_name in registry._tools.keys():
            if "mcp_multimodal_analyzer" in tool_name:
                tool_obj = registry._tools[tool_name]
                if getattr(tool_obj, "_model_name", None) == test_model:
                    found = True
                    break
        
        assert found, f"No multimodal tool found with model {test_model} in registry."
