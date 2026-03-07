import pytest
from unittest.mock import AsyncMock, patch
from nanobot.providers.base import LLMResponse
from strategery.patches.provider import ProviderPatch

@pytest.mark.asyncio
async def test_azure_openai_patch_logging_and_error_handling():
    # 1. Setup mock AzureOpenAIProvider
    # We mock the class itself because it might not be importable if upstream is missing it
    # But in our case, it is present.
    try:
        from nanobot.providers.azure_openai_provider import AzureOpenAIProvider
    except ImportError:
        pytest.skip("AzureOpenAIProvider not found in upstream")

    provider = AzureOpenAIProvider(api_key="test", api_base="https://test.openai.azure.com/", default_model="gpt-4")
    
    # 2. Apply patch
    patcher = ProviderPatch()
    patcher.apply({})

    # 3. Test successful chat
    with patch.object(AzureOpenAIProvider, "chat", new=AsyncMock(return_value=LLMResponse(content="Hello", finish_reason="stop"))) as mock_orig:
        # Re-apply patch to the instance if it was already patched on class
        # Actually, patcher.apply() patches the CLASS, so provider.chat is now the patched version.
        
        # We need to be careful: the patch replaces AzureOpenAIProvider.chat with _patched_chat
        # which calls _orig_chat_strategic.
        
        # Let's verify it was patched
        assert hasattr(AzureOpenAIProvider, "_orig_chat_strategic")
        
        response = await provider.chat(messages=[{"role": "user", "content": "hi"}])
        assert response.content == "Hello"
        # Verify it called the original (which we mocked as _orig_chat_strategic via the patch logic)
        # Wait, the patch logic does:
        # AzureOpenAIProvider._orig_chat_strategic = AzureOpenAIProvider.chat
        # AzureOpenAIProvider.chat = _patched_chat
        
    # 4. Test transient error retry
    transient_error = LLMResponse(content="503 Service Unavailable", finish_reason="error")
    success_response = LLMResponse(content="Recovered", finish_reason="stop")
    
    with patch.object(AzureOpenAIProvider, "_orig_chat_strategic", side_effect=[transient_error, success_response]) as mock_orig:
        with patch("strategery.patches.provider.asyncio.sleep", new=AsyncMock()) as mock_sleep:
            response = await provider.chat(messages=[{"role": "user", "content": "hi"}])
            assert response.content == "Recovered"
            assert mock_orig.call_count == 2
            assert mock_sleep.call_count == 1

    # 5. Test permanent error formatting
    permanent_error = LLMResponse(content="400 Bad Request: too many tokens", finish_reason="error")
    with patch.object(AzureOpenAIProvider, "_orig_chat_strategic", return_value=permanent_error) as mock_orig:
        response = await provider.chat(messages=[{"role": "user", "content": "hi"}])
        assert "[STRATEGIC]" in response.content
        assert "Context Overflow" in response.content
