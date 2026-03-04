import pytest
from unittest.mock import MagicMock, patch
import nanobot.agent.context
from nanobot.agent.context import ContextBuilder
from strategery.patches.config import ConfigPatch
from strategery.patches.subagent import SubagentPatch

def test_hardened_prompt_injection():
    """Verify that multiple patches successfully inject their mandates into the system prompt."""
    
    # 1. Reset class-level patch state
    if hasattr(ContextBuilder, "_orig_build_system_prompt_strategic"):
        ContextBuilder.build_system_prompt = ContextBuilder._orig_build_system_prompt_strategic
        del ContextBuilder._orig_build_system_prompt_strategic

    # 2. Setup Mock Instance
    mock_self = MagicMock()
    # We must provide the 'original' method on the instance for the patch to call
    mock_self._orig_build_system_prompt_strategic = MagicMock(return_value="Base System Prompt.")

    # 3. Apply Patch
    # We don't want to mock build_system_prompt during 'apply' because we want to test the wrapper
    # But we need to make sure 'apply' can find the class
    config_patch = ConfigPatch()
    config_patch.apply({})
    
    # Now ContextBuilder.build_system_prompt is the wrapper.
    # Call it with our mock_self
    final_prompt = ContextBuilder.build_system_prompt(mock_self)
    
    assert "Base System Prompt." in str(final_prompt)
    assert "🛡️ STRATEGIC MANDATE (MANDATORY)" in str(final_prompt)

def test_subagent_specialist_prompt_hardening():
    """Verify that subagents receive their specialist instructions."""
    from nanobot.agent.subagent import SubagentManager
    
    # 1. Reset class-level patch state
    if hasattr(SubagentManager, "_orig_build_subagent_prompt_strategic"):
        SubagentManager._build_subagent_prompt = SubagentManager._orig_build_subagent_prompt_strategic
        del SubagentManager._orig_build_subagent_prompt_strategic

    # 2. Setup Mock Instance
    mock_mgr = MagicMock()
    mock_mgr._orig_build_subagent_prompt_strategic = MagicMock(return_value="Subagent Base Prompt.")

    # 3. Apply Patch
    sub_patch = SubagentPatch()
    with patch("strategery.patches.subagent.strategic_logger"):
        sub_patch._patch_subagent_manager({})
        
        # Now call the patched method
        final_sub_prompt = SubagentManager._build_subagent_prompt(mock_mgr)
        
        assert "Subagent Base Prompt." in str(final_sub_prompt)
        assert "🛡️ STRATEGIC SPECIALIST INSTRUCTIONS" in str(final_sub_prompt)
