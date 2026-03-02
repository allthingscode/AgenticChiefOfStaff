import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import os
import sys

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from strategery.patches.subagent import SubagentPatch, strategic_select_specialist_model
from nanobot.agent.subagent import SubagentManager
from nanobot.agent.tools.registry import ToolRegistry

@pytest.fixture
def mock_specialist_config():
    return {
        "agents": {
            "specialists": {
                "researcher": {"model": "special-research-model", "keywords": ["research", "search", "verify"]},
                "architect": {"model": "special-architect-model", "keywords": ["architect", "design", "refactor"]}
            }
        }
    }

def test_strategic_select_specialist_model_deep(mock_specialist_config):
    """Exhaustive test of specialist model selection logic."""
    specs = mock_specialist_config["agents"]["specialists"]
    
    # 1. Direct keyword match (Researcher)
    assert strategic_select_specialist_model("research the codebase", None, specs) == "special-research-model"
    assert strategic_select_specialist_model("verify the state", "Verification", specs) == "special-research-model"
    
    # 2. Direct keyword match (Architect)
    assert strategic_select_specialist_model("architect the new feature", None, specs) == "special-architect-model"
    assert strategic_select_specialist_model("refactor the core", "Maintenance", specs) == "special-architect-model"
    
    # 3. Priority check (Researcher keywords vs Architect task)
    # The current logic checks Researcher keywords first in the 'if any' block for specific broad categories.
    # Actually, the loop over specs happens first.
    # In my config, 'researcher' is first.
    assert strategic_select_specialist_model("research and architect", None, specs) == "special-research-model"
    
    # 4. Fallback to broad categories
    # "analyze" is a broad researcher keyword
    assert strategic_select_specialist_model("analyze the logs", None, specs) == "special-research-model"
    # "implement" is a broad architect keyword
    assert strategic_select_specialist_model("implement the plan", None, specs) == "special-architect-model"
    
    # 5. Default (No match)
    assert strategic_select_specialist_model("say hello", "Greeting", specs) is None

@pytest.mark.asyncio
async def test_subagent_manager_integrated_routing(mock_specialist_config):
    """
    Integrated test to verify that SubagentManager temporarily switches models
    and uses the StrategicSubagentRegistry during execution.
    """
    # 1. Apply the patch
    patch_inst = SubagentPatch()
    
    # Forcibly reset existing patches to allow re-patching with mock config
    if hasattr(SubagentManager, "_orig_run_subagent_strategic"):
        delattr(SubagentManager, "_orig_run_subagent_strategic")
    if hasattr(SubagentManager, "_orig_announce_result_strategic"):
        delattr(SubagentManager, "_orig_announce_result_strategic")
    if hasattr(SubagentManager, "_orig_build_prompt_strategic"):
        delattr(SubagentManager, "_orig_build_prompt_strategic")

    with patch("strategery.patches.config.load_strategic_context", return_value=(None, "test@example.com", None)):
        # We also need to mock ToolRegistry.register to avoid loading real tools
        with patch.object(ToolRegistry, "register"):
            patch_inst.apply(mock_specialist_config)
    
    # 2. Setup mock SubagentManager
    mock_mgr = MagicMock(spec=SubagentManager)
    mock_mgr.model = "default-model"
    mock_mgr.bus = MagicMock()
    
    captured_models = []
    captured_registry_cls = []
    
    async def mock_orig_run(task_id, task, label, origin):
        # Capture state during original execution (which is now wrapped)
        captured_models.append(mock_mgr.model)
        import nanobot.agent.subagent
        captured_registry_cls.append(nanobot.agent.subagent.ToolRegistry)
        return None
    
    # Note: the patch assigns this to the class, so we need to ensure the mock has it
    mock_mgr._orig_run_subagent_strategic = mock_orig_run
    
    # 3. Execute Researcher Task
    await SubagentManager._run_subagent(mock_mgr, "task-1", "research the history", "Researcher", {"channel": "test", "chat_id": "123"})
    
    # 4. Verify Researcher Routing
    assert "special-research-model" in captured_models
    assert mock_mgr.model == "default-model" # Verified restoration
    
    # 5. Verify Specialist Registry Tagging
    # The registry class used during the subagent run should be our custom one
    specialist_registry_cls = captured_registry_cls[0]
    assert specialist_registry_cls.__name__ == "StrategicSubagentRegistry"
    
    # Create an instance to verify tagging
    reg_inst = specialist_registry_cls()
    assert getattr(reg_inst, "_is_strategic_specialist", False) is True

@pytest.mark.asyncio
async def test_subagent_registry_tool_access(mock_specialist_config):
    """Verify that high-power tools are ALLOWED for specialists but BLOCKED for others."""
    patch_inst = SubagentPatch()
    with patch("strategery.patches.config.load_strategic_context", return_value=(None, "test@example.com", None)):
        patch_inst.apply(mock_specialist_config)
    
    from nanobot.agent.tools.registry import ToolRegistry
    
    # 1. Main Agent Registry (Not tagged)
    main_reg = ToolRegistry()
    assert getattr(main_reg, "_is_strategic_specialist", False) is False
    
    mock_tool = MagicMock()
    mock_tool.name = "mcp_google-surgical_search"
    
    # Should be blocked
    with patch("strategery.patches.subagent.strategic_logger") as mock_log:
        main_reg.register(mock_tool)
        # Check if the registration was actually skipped (by checking if _orig_register was NOT called)
        # However, it's easier to check the log
        mock_log.debug.assert_any_call("Tool Stripping: Blocked registration of 'mcp_google-surgical_search' for Main Agent (forced delegation).")

    # 2. Specialist Registry (Mocking the behavior inside _run_subagent)
    # We simulate what happens inside _patched_run_subagent
    class SpecialistRegistry(ToolRegistry):
        def __init__(self, *args, **kwargs):
            self._is_strategic_specialist = True
            super().__init__(*args, **kwargs)
            
    spec_reg = SpecialistRegistry()
    assert getattr(spec_reg, "_is_strategic_specialist", False) is True
    
    with patch.object(ToolRegistry, "_orig_register_strategic") as mock_orig_reg:
        spec_reg.register(mock_tool)
        # Should NOT be blocked
        mock_orig_reg.assert_called_with(mock_tool)

@pytest.mark.asyncio
async def test_main_agent_tool_execution_block(mock_specialist_config):
    """Verify the hard block and circuit breaker on tool execution."""
    patch_inst = SubagentPatch()
    with patch("strategery.patches.config.load_strategic_context", return_value=(None, "test@example.com", None)):
        patch_inst.apply(mock_specialist_config)
    
    from nanobot.agent.tools.registry import ToolRegistry
    main_reg = ToolRegistry()
    
    # Attempt 1: Warning + Spawn hint
    res1 = await main_reg.execute("mcp_google-surgical_list_emails", {})
    assert "restricted to SPECIALIST subagents" in res1
    assert main_reg._strategic_block_attempts == 1
    
    # Attempt 2: Hard-Lock error
    res2 = await main_reg.execute("mcp_google-surgical_list_emails", {})
    assert "HARD-LOCKED" in res2
    assert main_reg._strategic_block_attempts == 2
