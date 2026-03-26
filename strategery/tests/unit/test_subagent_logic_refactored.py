from strategery.logic import subagent_logic


def test_role_blocks_logic():
    """Verify that role-based tool blocking still works after F-028 consolidation."""
    from unittest.mock import MagicMock

    # 1. Main Agent
    main_reg = MagicMock()
    main_reg._is_strategic_specialist = False
    assert subagent_logic.is_tool_blocked("mcp_google-surgical_list_tasks", main_reg) is True

    # 2. Researcher
    res_reg = MagicMock()
    res_reg._is_strategic_specialist = True
    res_reg._specialist_type = "researcher"
    assert subagent_logic.is_tool_blocked("git_add", res_reg) is True

    # 3. Architect
    arc_reg = MagicMock()
    arc_reg._is_strategic_specialist = True
    arc_reg._specialist_type = "architect"
    assert subagent_logic.is_tool_blocked("git_add", arc_reg) is False

    # Main Agent should be allowed
    assert not subagent_logic.is_tool_blocked("spawn", main_reg)

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
