import pytest
from nanobot.agent.loop import AgentLoop
from strategery.patches.provider import ProviderPatch

def test_reasoning_stripper_basic():
    """Test basic stripping of <think> tags."""
    text = "<think>I should do this.</think>Hello world"
    p = ProviderPatch()
    p._patch_agent_loop_cleaning()
    
    result = AgentLoop._strip_think(text)
    assert result == "Hello world"

def test_reasoning_stripper_markdown():
    """Test stripping of markdown-style thinking headers."""
    text = "**Thought:** I need to check the logs.\n\nHere is the log data."
    result = AgentLoop._strip_think(text)
    assert result == "Here is the log data."
    
    text2 = "*Thoughts:* This is complex.\n\nSolution: Use a patch."
    result2 = AgentLoop._strip_think(text2)
    assert result2 == "Solution: Use a patch."

def test_reasoning_stripper_plain_text():
    """Test stripping of plain text 'Thought:' headers."""
    text = "Thought: I am thinking.\n\nFinal Answer: 42"
    result = AgentLoop._strip_think(text)
    assert result == "Final Answer: 42"
    
    text2 = "Reasoning: Because of X.\n\nAction: Y"
    result2 = AgentLoop._strip_think(text2)
    assert result2 == "Action: Y"

def test_reasoning_stripper_mixed():
    """Test mixed tags and headers."""
    text = "<think>Tags</think>**Thought:** Markdown\n\nActual content"
    result = AgentLoop._strip_think(text)
    assert result == "Actual content"

def test_reasoning_stripper_circuit_breaker():
    """Test that 100% reasoning triggers the circuit breaker instead of returning None/Empty."""
    text = "<think>I am just thinking and have no final output.</think>"
    result = AgentLoop._strip_think(text)
    assert "[STRATEGIC: Your internal reasoning was captured." in result
    
    text2 = "**Thought:** Only thought here."
    result2 = AgentLoop._strip_think(text2)
    assert "[STRATEGIC: Your internal reasoning was captured." in result2

def test_reasoning_stripper_case_insensitivity():
    """Test that patterns are case-insensitive."""
    text = "THOUGHT: yelling thinking\n\nQuiet response"
    result = AgentLoop._strip_think(text)
    assert result == "Quiet response"
    
    text2 = "<THINK>loud tags</THINK>content"
    result2 = AgentLoop._strip_think(text2)
    assert result2 == "content"

def test_strategic_error_formatting():
    """Test that raw technical errors are converted to Strategic format."""
    from strategery.patches.provider import strategic_format_error
    
    e500 = "Error calling LLM: litellm.InternalServerError: Gemini 500"
    result = strategic_format_error(e500)
    assert "[STRATEGIC] Upstream Service Error (500)" in result
    
    e429 = "Rate limit exceeded (429)"
    result2 = strategic_format_error(e429)
    assert "[STRATEGIC] Capacity Limit Reached (429)" in result2
    
    e400 = "Too many tokens in context window"
    result3 = strategic_format_error(e400)
    assert "[STRATEGIC] Context Overflow (400)" in result3
