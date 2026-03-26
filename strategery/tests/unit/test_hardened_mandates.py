from strategery.logic import subagent_logic


def test_main_agent_log_root_mandate():
    """Verify that BUG-170 (Main Agent Log Path Hallucination) is addressed in delegation mandate."""
    base_prompt = "Base system prompt."
    hardened_prompt = subagent_logic.inject_delegation_mandate(base_prompt)

    assert "DEFINITIVE LOG ROOT (BUG-170)" in hardened_prompt
    assert subagent_logic.LOG_ROOT in hardened_prompt
    assert "Use this absolute path for all log audits" in hardened_prompt

def test_specialist_log_temporality_mandate():
    """Verify that BUG-166 (Specialist Log Context Drift) is addressed in specialist instructions."""
    base_prompt = "Base specialist prompt."
    hardened_prompt = subagent_logic.build_specialist_instructions(base_prompt, "researcher")

    assert "LOG AUDIT TEMPORALITY (BUG-166)" in hardened_prompt
    assert "filter for the current date" in hardened_prompt
    assert "Reporting stale errors" in hardened_prompt

def test_specialist_definitive_log_root_mandate():
    """Verify that BUG-167 (Log Path Ambiguity) is addressed in specialist instructions."""
    base_prompt = "Base specialist prompt."
    hardened_prompt = subagent_logic.build_specialist_instructions(base_prompt, "researcher")

    assert "DEFINITIVE LOG ROOT (BUG-167)" in hardened_prompt
    # Use the dynamic LOG_ROOT from the logic module
    assert subagent_logic.LOG_ROOT in hardened_prompt

    assert "EXCLUSIVELY" in hardened_prompt
