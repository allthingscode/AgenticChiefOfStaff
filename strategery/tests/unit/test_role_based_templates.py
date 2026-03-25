from strategery.logic import subagent_logic

def test_build_specialist_instructions_researcher():
    """Verify that a Researcher subagent receives only relevant instructions."""
    base = "Base prompt."
    # We call the logic function directly
    prompt = subagent_logic.build_specialist_instructions(base, "researcher")
    
    assert "## RESEARCHER SPECIALIST MANDATE" in prompt
    assert "EMAIL ATTACHMENT RESTRICTION" in prompt # Researcher specific
    assert "RECURSION MANDATE" in prompt # Researcher specific
    assert "CALENDAR MANDATE" in prompt # Researcher specific
    
    # Should NOT contain Architect specific rules
    assert "MARKDOWN DIRECTIVE MANDATE" not in prompt
    assert "PYTHON EXECUTION (MANDATE - BUG-141)" not in prompt
    assert "SOP-001 (Unit Tests)" not in prompt

def test_build_specialist_instructions_architect():
    """Verify that an Architect subagent receives only relevant instructions."""
    base = "Base prompt."
    prompt = subagent_logic.build_specialist_instructions(base, "architect")
    
    assert "## ARCHITECT SPECIALIST MANDATE" in prompt
    assert "MARKDOWN DIRECTIVE MANDATE" in prompt # Architect specific
    assert "PYTHON EXECUTION (MANDATE - BUG-141)" in prompt # Architect specific
    assert "SOP-001 (Unit Tests)" in prompt # Architect specific
    
    # Should NOT contain Researcher specific rules
    assert "EMAIL ATTACHMENT RESTRICTION" not in prompt
    assert "CALENDAR MANDATE" not in prompt

def test_build_specialist_instructions_global_rules():
    """Verify that both roles receive global rules."""
    base = "Base prompt."
    res_prompt = subagent_logic.build_specialist_instructions(base, "researcher")
    arc_prompt = subagent_logic.build_specialist_instructions(base, "architect")
    
    global_marker = "STATELESS SHELL MANDATE (CRITICAL)"
    assert global_marker in res_prompt
    assert global_marker in arc_prompt
    
    finality_marker = "FINALITY MANDATE"
    assert finality_marker in res_prompt
    assert finality_marker in arc_prompt
