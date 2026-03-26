import pytest

from strategery.logic import provider_logic


def test_format_provider_log():
    res = provider_logic.format_provider_log("TestProvider", "test-model")
    assert res == "TestProvider request: model=test-model"

def test_format_strategic_error_context():
    err = "Error: context_length exceeded for this model"
    res = provider_logic.format_strategic_error(err)
    assert "[STRATEGIC] Context Overflow" in res

def test_format_strategic_error_rate_limit():
    err = "RateLimitError: 429 Too Many Requests"
    res = provider_logic.format_strategic_error(err)
    assert "Capacity Limit Reached (429)" in res

def test_strip_reasoning_artifacts_tags():
    text = "<think>Internal reasoning</think>Final answer"
    res = provider_logic.strip_reasoning_artifacts(text)
    assert res == "Final answer"

def test_strip_reasoning_artifacts_headers():
    text = "**Thoughts:** I should do X.\n\nFinal answer"
    res = provider_logic.strip_reasoning_artifacts(text)
    assert res == "Final answer"

def test_strip_reasoning_circuit_breaker():
    text = "<think>Only reasoning</think>"
    res = provider_logic.strip_reasoning_artifacts(text)
    assert "[STRATEGIC: Your internal reasoning was captured" in res

@pytest.mark.asyncio
async def test_run_strategic_embedding_empty_key():
    # Verify that it handles errors gracefully and doesn't crash the bot
    res = await provider_logic.run_strategic_embedding("", "invalid-model", "test text")
    assert res == []
