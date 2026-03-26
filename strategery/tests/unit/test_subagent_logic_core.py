from unittest.mock import MagicMock
from strategery.logic import subagent_logic
from strategery.logic.config_logic import validate_strategic_config


def test_is_tool_blocked_main_agent():
    # Mock registry for Main Agent
    reg = MagicMock()
    reg._is_strategic_specialist = False
    
    assert subagent_logic.is_tool_blocked("google", reg) is True
    assert subagent_logic.is_tool_blocked("read_file", reg) is True
    assert subagent_logic.is_tool_blocked("exec", reg) is False

def test_is_tool_blocked_specialist():
    # Mock registry for specialist
    reg = MagicMock()
    reg._is_strategic_specialist = True
    reg._specialist_type = "researcher"
    
    # Specialists should be blocked from 'spawn'
    assert subagent_logic.is_tool_blocked("spawn", reg) is True
    # Specialists should be allowed to use 'read_file'
    assert subagent_logic.is_tool_blocked("read_file", reg) is False

def test_detect_mandate_bypass():
    assert subagent_logic.detect_mandate_bypass("cat history.md") is True
    assert subagent_logic.detect_mandate_bypass("ping 8.8.8.8") is True
    # MANDATE: All agents are blocked from using 'ls ' in raw shell to bypass FS tools
    assert subagent_logic.detect_mandate_bypass("ls -la") is True

def test_get_specialist_model_researcher():
    config = validate_strategic_config({"agents": {"specialists": {"researcher": {"model": "flash-lite"}}}})
    res = subagent_logic.get_specialist_model("researcher", config, "default")
    assert res == "flash-lite"

def test_get_specialist_model_architect():
    config = validate_strategic_config({"agents": {"specialists": {"architect": {"model": "pro-v1"}}}})
    res = subagent_logic.get_specialist_model("architect", config, "default")
    assert res == "pro-v1"

def test_get_specialist_model_fallback():
    config = validate_strategic_config({})
    res = subagent_logic.get_specialist_model("invalid", config, "default")
    assert res == "default"

def test_format_spawn_termination_directive():
    res = subagent_logic.format_spawn_termination_directive("Subagent started", "abc-123")
    assert "abc-123" in res
    assert "### ⚖️ STRATEGIC MANDATE: STOP Turn" in res

def test_inject_delegation_mandate():
    content = "Base system prompt."
    res = subagent_logic.inject_delegation_mandate(content)
    assert "DELEGATE BY DEFAULT" in res
    assert "Base system prompt." in res

def test_build_specialist_instructions():
    res = subagent_logic.build_specialist_instructions("Base.", "researcher")
    assert "RESEARCHER SPECIALIST MANDATE" in res
    assert "SEARCH MANDATE" in res
