from strategery.logic import subagent_logic

def test_circuit_breaker_provides_guidance():
    """Verify that BUG-169 self-correction guidance is in the error message."""
    breaker = subagent_logic.ToolCircuitBreaker(limit=2)
    
    # 1. First Attempt
    res1 = breaker.check("exec", {"command": "ls"})
    assert res1 is None
    
    # 2. Second Attempt -> LOOP
    res2 = breaker.check("exec", {"command": "ls"})
    assert res2 is not None
    assert "SELF-CORRECTION GUIDANCE" in res2
    assert "VARY YOUR PARAMS" in res2
    assert "SWITCH TOOLS" in res2
    assert "VERIFY FIRST" in res2
    assert "CHECK DELIMITERS" in res2
