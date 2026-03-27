import asyncio
import re
from typing import Any

from strategery.strategic_logger import strategic_logger


def format_provider_log(provider_name: str, model: str) -> str:
    """Formats the provider request log string."""
    return f"{provider_name} request: model={model}"

def format_strategic_error(error_text: str) -> str:
    """Intercepts raw technical error strings and converts them to Strategic format."""
    # 1. SPECIFIC KEYWORDS (High Precision)
    if any(x in error_text for x in ["too many tokens", "context_length", "context window"]):
        return "[STRATEGIC] Context Overflow (400): The conversation history has exceeded the model's limits. Try a shorter message."

    # 2. STATUS CODES & EXCEPTIONS
    if "InternalServerError" in error_text or "500" in error_text:
        return "[STRATEGIC] Upstream Service Error (500): The AI provider is currently unstable. Please wait a moment and try again."
    if "RateLimitError" in error_text or "429" in error_text:
        return "[STRATEGIC] Capacity Limit Reached (429): You have hit the provider's rate limit. Throttling active."
    if "InvalidRequestError" in error_text or "400" in error_text:
        return f"[STRATEGIC] Request Denied (400): The provider rejected the payload formatting. Details: {error_text[:100]}..."

    return f"[STRATEGIC] Provider Communication Failure: {error_text[:150]}"

async def run_strategic_embedding(api_key: str, model_name: str, input_text: str) -> list:
    """
    Standalone logic for Google GenAI embedding with strategic logging and retries.
    """
    # STRATEGIC DEFAULT (MANDATE)
    STRATEGIC_FALLBACK_MODEL = "models/gemini-embedding-001"

    if not api_key:
        strategic_logger.error("Strategic Embedding: No API key provided.")
        return []

    if not input_text or not input_text.strip():
        strategic_logger.warning("Strategic Embedding: No input text provided.")
        return []

    # MANDATE (BUG-261 / BUG-264): Pre-emptive fallback for known-bad or invalid models
    bad_patterns = ["invalid", "text-embedding-004", "embedding-001", "gecko-001"]
    if not model_name or any(p in model_name.lower() for p in bad_patterns):
        if model_name != STRATEGIC_FALLBACK_MODEL:
            strategic_logger.warning(f"Pre-emptive Fallback: Model '{model_name}' blacklisted. Using {STRATEGIC_FALLBACK_MODEL}.")
        model_name = STRATEGIC_FALLBACK_MODEL

    try:
        from google import genai
        max_retries = 5
        retry_delay = 2.0

        for attempt in range(max_retries):
            try:
                strategic_logger.info(f"GoogleGenAI embed: model={model_name}")
                # MANDATE: Constructor moved inside retry loop to handle transient initialization failures
                client = genai.Client(api_key=api_key)

                # USE ASYNC CLIENT: client.aio.models.embed_content
                # BUG-264: Input text MUST be a list (contents=[...])
                result = await client.aio.models.embed_content(
                    model=model_name,
                    contents=[input_text]
                )
                return [item.values for item in result.embeddings]
            except Exception as api_err:
                err_str = str(api_err)
                
                # REACTIVE FALLBACK (BUG-264): If 404 occurs, switch to fallback model mid-retry
                if any(x in err_str for x in ["404", "NOT_FOUND", "not found"]):
                    if model_name != STRATEGIC_FALLBACK_MODEL:
                        strategic_logger.warning(f"Reactive Fallback: Detected 404 for '{model_name}'. Switching to {STRATEGIC_FALLBACK_MODEL}.")
                        model_name = STRATEGIC_FALLBACK_MODEL
                        # We don't sleep here, just retry immediately with the new model
                        continue

                # DO NOT retry on other 400/401/403 or Validation errors (Permanent)
                permanent_errors = [
                    "400", "401", "403", "INVALID_ARGUMENT", "PERMISSION_DENIED", 
                    "API_KEY_INVALID", "ValidationError", "ValueError"
                ]
                if any(x in err_str for x in permanent_errors):
                    strategic_logger.error(f"Permanent Embedding API Error: {api_err}")
                    raise api_err

                if attempt == max_retries - 1:
                    # Final attempt failed
                    raise api_err

                strategic_logger.warning(f"Embedding API attempt {attempt + 1} failed: {api_err}. Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff

    except Exception as e:
        strategic_logger.error(f"Strategic Embedding Error: {e}")
        return []

def strip_reasoning_artifacts(text: str | None) -> str | None:
    """Aggressively strips reasoning artifacts (<thought>, <think>, etc)."""
    if not text: return None

    # 1. CORE & EXTENDED: Strip <think> and <thought> tags (and their contents)
    res = re.sub(r"<(think|thought)>[\s\S]*?</\1>", "", text, flags=re.IGNORECASE).strip()

    # 2. STRATEGIC: Strip markdown-style and plain-text thinking headers
    patterns = [
        r"\*\*(Thought|Thoughts|Reasoning|Internal Thought)s?[\.:]?\*\*[\s\S]*?(?=\n\n|\Z)",
        r"\*(Thought|Thoughts|Reasoning|Internal Thought)s?[\.:]?\*[\s\S]*?(?=\n\n|\Z)",
        r"^(Thought|Thoughts|Reasoning|Internal Thought)s?[\.:]?[\s\S]*?(?=\n\n|\Z)"
    ]
    for pattern in patterns:
        res = re.sub(pattern, "", res, flags=re.IGNORECASE | re.MULTILINE).strip()

    # 3. STRATEGIC: Strip trailing reasoning markers and cleanup
    res = re.sub(r"\s+(thought|reasoning)[\.:]?$", "", res, flags=re.IGNORECASE)
    res = re.sub(r"</?(think|thought)>", "", res, flags=re.IGNORECASE).strip()

    # 4. CIRCUIT BREAKER (Idle Loop Prevention):
    if not res and text.strip():
        # If the text is one of our Strategic Error blocks, don't trigger the circuit breaker!
        if "[STRATEGIC]" in text:
            return text

        strategic_logger.warning("Reasoning Stripper: Response was 100% reasoning. Applying circuit breaker.")
        return "[STRATEGIC: Your internal reasoning was captured. You MUST now provide a final response to the user or execute a permitted tool call. DO NOT repeat internal thought blocks.]"

    return res or None

def safe_parse_litellm_response(response: Any) -> Any:
    """ Validates that a LiteLLM response has at least one choice. """
    if not hasattr(response, "choices") or not response.choices or len(response.choices) == 0:
        # Create a mock choice with an error message to prevent IndexError
        class MockChoice:
            def __init__(self):
                class MockMessage:
                    def __init__(self):
                        self.content = "[STRATEGIC] The provider returned an empty response (Zero Choices). This usually indicates a safety filter or upstream refusal."
                        self.tool_calls = None
                self.message = MockMessage()
                self.finish_reason = "error"

        # Inject the mock choice into the response object
        response.choices = [MockChoice()]
        strategic_logger.warning("LiteLLM Safe Parse: Detected empty choices. Injected strategic error choice.")
    return response
