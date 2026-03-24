import inspect
import pytest
from unittest.mock import MagicMock
from nanobot.agent.loop import AgentLoop
from strategery.patches import registry
from strategery.patches.base import PatchContext

@pytest.fixture(autouse=True)
def apply_patches():
    context = PatchContext(
        config=MagicMock(),
        storage_root="D:/Nanobot_Storage",
        user_email="test@example.com",
        app_root="C:/test"
    )
    registry.apply_all(context)

def test_process_message_signature_consistency():
    """Verify that all patches keep _process_message signature compatible with core."""
    core_sig = inspect.signature(AgentLoop._process_message)
    
    # Core expects: (self, msg, *, on_progress=None, session_key=None)
    # But wait, let's check what it actually is in the current environment after patches
    
    current_sig = inspect.signature(AgentLoop._process_message)
    params = list(current_sig.parameters.values())
    
    # Standard: self (0), msg (1), on_progress (2), session_key (3) or **kwargs
    assert len(params) >= 2
    assert params[1].name == "msg"
    
    # Check for **kwargs support in patched version
    has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)
    assert has_kwargs, "Patched _process_message MUST support **kwargs for cross-patch compatibility"

def test_run_agent_loop_signature_consistency():
    """Verify that all patches keep _run_agent_loop signature compatible with core."""
    current_sig = inspect.signature(AgentLoop._run_agent_loop)
    params = list(current_sig.parameters.values())
    
    # Core expects: (self, initial_messages, on_progress=None)
    assert len(params) >= 2
    assert params[1].name == "initial_messages"
    
    has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)
    assert has_kwargs, "Patched _run_agent_loop MUST support **kwargs for cross-patch compatibility"
