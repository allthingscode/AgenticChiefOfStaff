"""
GOLDEN RECORD: Specialist Economy Enforcement
Goal: Ensure 100% deterministic tool visibility across roles.
Mandate: Prevent 'High-Power Leakage' to the Main Agent.
"""
import pytest

from nanobot.agent.tools.registry import ToolRegistry
from strategery.patches.subagent import SubagentPatch


@pytest.fixture
def registry_factory(mock_context):
    """Returns a factory for creating role-aware registries."""
    # MANDATE: We must apply the patch so that get_definitions is monkey-patched
    patch_inst = SubagentPatch()
    patch_inst.apply(mock_context)

    def _create(role="main"):
        reg = ToolRegistry()
        if role == "specialist" or role == "researcher":
            reg._is_strategic_specialist = True
            reg._specialist_type = "researcher"
        elif role == "architect":
            reg._is_strategic_specialist = True
            reg._specialist_type = "architect"
        return reg
    return _create

@pytest.mark.parametrize("tool_name, role, expected_visible", [
    # Main Agent Blocklist
    ("google", "main", False),
    ("ai-search", "main", False),
    ("email-reporter", "main", False),
    ("strategic_", "main", False),
    ("web_search", "main", False),
    ("read_file", "main", False),
    ("write_file", "main", False),
    ("spawn", "main", True), # Main agent MUST see spawn

    # Specialist Access
    ("google", "specialist", True),
    ("ai-search", "specialist", True),
    ("email-reporter", "specialist", True),
    ("strategic_", "specialist", True),
    ("read_file", "specialist", True),
    ("spawn", "specialist", False), # Specialists are FORBIDDEN from nested spawning
])
def test_tool_visibility_golden_record(registry_factory, tool_name, role, expected_visible):
    """Verifies that tool stripping correctly enforces the Specialist Economy."""
    reg = registry_factory(role)

    # Mock a tool object
    class MockTool:
        def __init__(self, name):
            self.name = name
        def to_schema(self):
            return {"type": "function", "function": {"name": self.name}}

    # Register the tool
    reg.register(MockTool(tool_name))

    # Check visibility in definitions
    defs = reg.get_definitions()
    visible_names = [d.get("function", {}).get("name", "").lower() for d in defs]

    is_visible = any(tool_name.lower() in name for name in visible_names)

    assert is_visible == expected_visible, f"Tool '{tool_name}' visibility mismatch for role '{role}'. Expected: {expected_visible}, Got: {is_visible}"

def test_main_agent_blocked_path_patterns(registry_factory):
    """Verifies that path manipulation patterns are blocked for the Main Agent."""
    reg = registry_factory("main")

    blocked_patterns = ["ls ", "dir ", "D:", "filesystem-d"]

    for pattern in blocked_patterns:
        class MockTool:
            def __init__(self, name): self.name = name
            def to_schema(self): return {"type": "function", "function": {"name": self.name}}

        reg.register(MockTool(pattern))
        defs = reg.get_definitions()
        visible_names = [d.get("function", {}).get("name", "").lower() for d in defs]

        assert not any(pattern.lower() in name for name in visible_names), f"Pattern '{pattern}' leaked to Main Agent visibility!"
