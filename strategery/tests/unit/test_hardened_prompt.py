from pathlib import Path
from unittest.mock import MagicMock, patch

from strategery.patches.config import ConfigPatch
from strategery.patches.subagent import SubagentPatch


def test_hardened_system_prompt():
    """Verify that the system prompt includes Specialist Economy mandates."""
    from nanobot.agent.context import ContextBuilder

    # 1. Reset class-level patch state
    if hasattr(ContextBuilder, "_orig_build_system_prompt_strategic"):
        ContextBuilder.build_system_prompt = ContextBuilder._orig_build_system_prompt_strategic
        del ContextBuilder._orig_build_system_prompt_strategic

    # 2. Apply Patch
    from strategery.patches.base import PatchContext
    context = PatchContext(
        config={},
        storage_root=Path("/tmp/storage"),
        user_email="test@user.com",
        app_root=Path("/tmp/app")
    )
    patch_obj = ConfigPatch()
    # Apply global patches including ContextBuilder
    patch_obj.apply(context)

    # 3. Test
    builder = ContextBuilder(workspace=Path("/tmp"))
    # build_system_prompt is called by build_messages or directly
    system_msg = builder.build_system_prompt()

    assert "## 🛡️ STRATEGIC MANDATE (MANDATORY)" in system_msg
    assert "DELEGATION" in system_msg

def test_subagent_specialist_prompt_hardening():
    """Verify that subagents receive their specialist instructions."""
    from nanobot.agent.subagent import SubagentManager

    # 1. Reset class-level patch state
    if hasattr(SubagentManager, "_orig_build_subagent_prompt_strategic"):
        SubagentManager._build_subagent_prompt = SubagentManager._orig_build_subagent_prompt_strategic
        del SubagentManager._orig_build_subagent_prompt_strategic

    # 2. Setup Mock Instance
    mock_mgr = MagicMock()
    # Mock the original method to return a string
    mock_mgr._orig_build_subagent_prompt_strategic = MagicMock(return_value="Subagent Base Prompt.")

    # 3. Apply Patch
    sub_patch = SubagentPatch()
    with patch("strategery.patches.subagent.strategic_logger"):
        sub_patch._patch_subagent_manager({})

        # Now call the patched method directly on the class with our mock instance
        final_sub_prompt = SubagentManager._build_subagent_prompt(mock_mgr)

        assert "Subagent Base Prompt." in final_sub_prompt
        assert "## RESEARCHER SPECIALIST MANDATE" in final_sub_prompt
        assert "STRATEGIC SPECIALIST INSTRUCTIONS" in final_sub_prompt
