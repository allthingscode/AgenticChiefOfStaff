from strategery.logic import subagent_logic

def test_role_blocks_logic():
    """Verify that role-based tool blocking still works after F-028 consolidation."""
    # Main Agent should be blocked from google-surgical
    assert subagent_logic.is_tool_blocked("mcp_google-surgical_list_tasks", is_specialist=False)
    # Specialist should be allowed
    assert not subagent_logic.is_tool_blocked("mcp_google-surgical_list_tasks", is_specialist=True)
    
    # Specialist should be blocked from spawn
    assert subagent_logic.is_tool_blocked("spawn", is_specialist=True)
    # Main Agent should be allowed
    assert not subagent_logic.is_tool_blocked("spawn", is_specialist=False)

def test_telemetry_formatter():
    """Verify that the new _format_telemetry helper works correctly."""
    label = "TestAgent"
    event = "TEST_EVENT"
    content = {"key": "value"}
    
    formatted = subagent_logic._format_telemetry(label, event, content)
    assert "[TestAgent] TEST_EVENT:" in formatted
    assert "key" in formatted
    assert "value" in formatted
    
    # Test with string content
    formatted_str = subagent_logic._format_telemetry(label, event, "simple text")
    assert "simple text" in formatted_str

def test_clutter_stripping_performance():
    """Verify that pre-compiled regex still strips correctly."""
    raw = "chcp 65001; ls"
    hardened = subagent_logic.harden_subagent_command(raw)
    assert "chcp 65001" not in hardened
    assert "ls" in hardened
