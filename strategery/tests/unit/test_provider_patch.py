import pytest
from nanobot.agent.loop import AgentLoop
from strategery.patches.provider import ProviderPatch
from strategery.logic import provider_logic

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
    e500 = "Error calling LLM: litellm.InternalServerError: Gemini 500"
    result = provider_logic.format_strategic_error(e500)
    assert "[STRATEGIC] Upstream Service Error (500)" in result
    
    e429 = "Rate limit exceeded (429)"
    result2 = provider_logic.format_strategic_error(e429)
    assert "[STRATEGIC] Capacity Limit Reached (429)" in result2
    
    e400 = "Too many tokens in context window"
    result3 = provider_logic.format_strategic_error(e400)
    assert "[STRATEGIC] Context Overflow (400)" in result3

def test_provider_base_patch():
    """Verify that LLMProvider base class is patched with strategic embedding."""
    from nanobot.providers.base import LLMProvider
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.providers.custom_provider import CustomProvider
    
    p = ProviderPatch()
    p._patch_base_provider()
    p._patch_litellm_provider()
    
    # 1. Base class should have it
    assert hasattr(LLMProvider, "embed")
    assert LLMProvider.embedding_model == "models/gemini-embedding-001"
    
    # 2. Inherited instances should have it
    lite_p = LiteLLMProvider(api_key="test")
    assert hasattr(lite_p, "embed")
    
    custom_p = CustomProvider(api_key="test")
    assert hasattr(custom_p, "embed")

@pytest.mark.asyncio
async def test_litellm_retry_transient():
    """Verify that LiteLLMProvider.chat retries on transient errors."""
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.providers.base import LLMResponse
    from unittest.mock import AsyncMock, patch
    
    p = ProviderPatch()
    p._patch_litellm_provider()
    
    # Mock the original chat to return 500 twice, then success
    mock_response_500 = LLMResponse(content="Internal Server Error (500)", finish_reason="error")
    mock_response_ok = LLMResponse(content="Success!", finish_reason="stop")
    
    with patch.object(LiteLLMProvider, "_orig_chat_strategic", new_callable=AsyncMock) as mock_orig:
        mock_orig.side_effect = [mock_response_500, mock_response_500, mock_response_ok]
        
        provider = LiteLLMProvider(api_key="test")
        # Reduce retry delay for test speed
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            res = await provider.chat(messages=[{"role": "user", "content": "hi"}])
            
            assert res.content == "Success!"
            assert mock_orig.call_count == 3
            assert mock_sleep.call_count == 2

@pytest.mark.asyncio
async def test_litellm_permanent_fail_no_retry():
    """Verify that LiteLLMProvider.chat does NOT retry on permanent errors (400)."""
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.providers.base import LLMResponse
    from unittest.mock import AsyncMock, patch
    
    p = ProviderPatch()
    p._patch_litellm_provider()
    
    mock_response_400 = LLMResponse(content="Invalid Request (400)", finish_reason="error")
    
    with patch.object(LiteLLMProvider, "_orig_chat_strategic", new_callable=AsyncMock) as mock_orig:
        mock_orig.return_value = mock_response_400
        
        provider = LiteLLMProvider(api_key="test")
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            res = await provider.chat(messages=[{"role": "user", "content": "hi"}])
            
            assert "[STRATEGIC] Request Denied (400)" in res.content
            assert mock_orig.call_count == 1
            assert mock_sleep.call_count == 0

@pytest.mark.asyncio
async def test_litellm_exception_retry():
    """Verify that LiteLLMProvider.chat retries on transient exceptions."""
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.providers.base import LLMResponse
    from unittest.mock import AsyncMock, patch
    
    p = ProviderPatch()
    p._patch_litellm_provider()
    
    with patch.object(LiteLLMProvider, "_orig_chat_strategic", new_callable=AsyncMock) as mock_orig:
        mock_orig.side_effect = [
            Exception("503 Service Unavailable"), 
            LLMResponse(content="Finally!", finish_reason="stop")
        ]
        
        provider = LiteLLMProvider(api_key="test")
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            res = await provider.chat(messages=[{"role": "user", "content": "hi"}])
            
            assert res.content == "Finally!"
            assert mock_orig.call_count == 2
            assert mock_sleep.call_count == 1
