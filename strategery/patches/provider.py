import os
import re
import asyncio
from . import BasePatch
from strategery.strategic_logger import strategic_logger

def strategic_log_provider_request(provider_name, model):
    """Logs LLM requests at the INFO level for strategic visibility."""
    strategic_logger.info(f"{provider_name} request: model={model}")

def strategic_format_error(error_text: str) -> str:
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

async def strategic_litellm_embed(self, input_text):
    """
    Standalone wrapper for Google GenAI embedding with strategic logging and retries.
    Used by StrategicVectorStore to bypass LiteLLM's sometimes inconsistent embedding routing.
    """
    try:
        from google import genai
        # MANDATE: Fallback to models/gemini-embedding-001 if not set
        model_name = getattr(self, "embedding_model", "models/gemini-embedding-001")
        strategic_logger.info(f"GoogleGenAI embed: model={model_name}")
        
        max_retries = 5
        retry_delay = 2.0
        
        for attempt in range(max_retries):
            try:
                # MANDATE: Constructor moved inside retry loop to handle transient initialization failures
                client = genai.Client(api_key=self.api_key)
                
                # USE ASYNC CLIENT: client.aio.models.embed_content
                result = await client.aio.models.embed_content(
                    model=model_name,
                    contents=input_text
                )
                return [item.values for item in result.embeddings]
            except Exception as api_err:
                err_str = str(api_err)
                # DO NOT retry on 400/401/403 errors (Permanent)
                if any(x in err_str for x in ["400", "401", "403", "INVALID_ARGUMENT", "PERMISSION_DENIED", "API_KEY_INVALID"]):
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

class ProviderPatch(BasePatch):
    """Handles provider-level logging, routing, error interception, and response cleaning."""
    
    @property
    def name(self) -> str:
        return "Provider Logging & Routing"

    def apply(self, config_data: dict) -> bool:
        try:
            self._patch_base_provider()
            self._patch_litellm_provider()
            self._patch_azure_openai_provider()
            self._patch_agent_loop_cleaning()
            return True
        except Exception as e:
            strategic_logger.error(f"Provider patch error: {e}")
            return False

    def _patch_azure_openai_provider(self):
        try:
            from nanobot.providers.azure_openai_provider import AzureOpenAIProvider
        except ImportError:
            strategic_logger.debug("AzureOpenAIProvider not found in upstream. Skipping patch.")
            return

        if not hasattr(AzureOpenAIProvider, "_orig_chat_strategic"):
            AzureOpenAIProvider._orig_chat_strategic = AzureOpenAIProvider.chat
            
            async def _patched_chat(self, *args, **kwargs):
                model = kwargs.get("model") or (args[2] if len(args) > 2 else self.default_model)
                strategic_log_provider_request("AzureOpenAI", model)
                
                max_retries = 3
                retry_delay = 2.0
                
                for attempt in range(max_retries):
                    try:
                        response = await self._orig_chat_strategic(*args, **kwargs)
                        if getattr(response, "finish_reason", None) == "error":
                            raw_content = str(response.content)
                            is_transient = any(x in raw_content for x in ["500", "503", "504", "InternalServerError", "ServiceUnavailable", "RateLimitError", "429", "timeout"])
                            if is_transient and attempt < max_retries - 1:
                                strategic_logger.warning(f"Transient Azure error detected ({raw_content[:50]}). Attempt {attempt + 1}/{max_retries}. Retrying in {retry_delay}s...")
                                await asyncio.sleep(retry_delay)
                                retry_delay *= 2
                                continue
                            response.content = strategic_format_error(raw_content)
                        return response
                    except Exception as e:
                        err_str = str(e)
                        is_transient = any(x in err_str for x in ["500", "503", "InternalServerError", "ServiceUnavailable", "RateLimit", "429", "Timeout"])
                        if is_transient and attempt < max_retries - 1:
                            strategic_logger.warning(f"AzureOpenAI Exception (Transient): {err_str[:50]}. Retrying...")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2
                            continue
                        strategic_logger.error(f"AzureOpenAI Fatal Crash: {e}")
                        from nanobot.providers.base import LLMResponse
                        return LLMResponse(content=strategic_format_error(err_str), finish_reason="error")
            
            AzureOpenAIProvider.chat = _patched_chat
            strategic_logger.debug("Patched AzureOpenAIProvider with strategic logging and retries.")

    def _patch_base_provider(self):
        from nanobot.providers.base import LLMProvider
        
        # 1. Attach Embedding Method & Model to BASE class
        # This ensures all providers (LiteLLM, Custom, etc) have it.
        if not hasattr(LLMProvider, "embed"):
            LLMProvider.embed = strategic_litellm_embed
            LLMProvider.embedding_model = "models/gemini-embedding-001"
            strategic_logger.debug("Patched LLMProvider base with strategic embedding.")

    def _patch_litellm_provider(self):
        from nanobot.providers.litellm_provider import LiteLLMProvider
        
        # 0. DEFENSIVE (BUG-030): Attach embed directly to LiteLLMProvider as well
        if not hasattr(LiteLLMProvider, "embed"):
            LiteLLMProvider.embed = strategic_litellm_embed
            LiteLLMProvider.embedding_model = "models/gemini-embedding-001"
            strategic_logger.debug("Patched LiteLLMProvider class directly with strategic embedding.")

        # 1. Patch Chat for Logging & Retries
        if not hasattr(LiteLLMProvider, "_orig_chat_strategic"):
            LiteLLMProvider._orig_chat_strategic = LiteLLMProvider.chat
            
            async def _patched_chat(self, *args, **kwargs):
                # Handle both positional and keyword arguments for 'model'
                # Signature: (self, messages, tools=None, model=None, ...)
                model = kwargs.get("model") or (args[1] if len(args) > 1 else None)
                if not model:
                    # Look deeper if it's passed via args (index 2 because self is index 0 in the original call but args here doesn't include self if called via instance)
                    # Actually, when we patch LiteLLMProvider.chat = _patched_chat, 'self' IS passed as args[0]
                    model = args[2] if len(args) > 2 else "unknown"
                
                strategic_log_provider_request("LiteLLM", model)
                
                max_retries = 3
                retry_delay = 2.0
                
                for attempt in range(max_retries):
                    try:
                        response = await self._orig_chat_strategic(*args, **kwargs)
                        
                        # Intercept error responses returned as successful calls (LiteLLM pattern)
                        if getattr(response, "finish_reason", None) == "error":
                            raw_content = str(response.content)
                            
                            # 1. CATEGORIZE ERROR
                            is_transient = any(x in raw_content for x in ["500", "503", "504", "InternalServerError", "ServiceUnavailable", "RateLimitError", "429", "timeout"])
                            is_permanent = any(x in raw_content for x in ["400", "401", "403", "InvalidRequestError", "ContextWindow", "too many tokens", "API_KEY_INVALID", "PERMISSION_DENIED"])
                            
                            # 2. RETRY IF TRANSIENT
                            if is_transient and attempt < max_retries - 1:
                                strategic_logger.warning(f"Transient error detected ({raw_content[:50]}). Attempt {attempt + 1}/{max_retries}. Retrying in {retry_delay}s...")
                                await asyncio.sleep(retry_delay)
                                retry_delay *= 2
                                continue
                            
                            # 3. FORMAT AND RETURN IF PERMANENT OR LAST ATTEMPT
                            if is_permanent:
                                strategic_logger.error(f"Permanent Provider Error: {raw_content[:100]}")
                            elif attempt == max_retries - 1:
                                strategic_logger.error(f"Exhausted retries for transient error: {raw_content[:100]}")
                                
                            response.content = strategic_format_error(raw_content)
                            
                        return response

                    except Exception as e:
                        err_str = str(e)
                        is_transient = any(x in err_str for x in ["500", "503", "InternalServerError", "ServiceUnavailable", "RateLimit", "429", "Timeout"])
                        
                        if is_transient and attempt < max_retries - 1:
                            strategic_logger.warning(f"LiteLLM Exception (Transient): {err_str[:50]}. Retrying...")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2
                            continue
                            
                        # Catch-all for unexpected provider crashes or final failures
                        strategic_logger.error(f"LiteLLM Fatal Crash: {e}")
                        from nanobot.providers.base import LLMResponse
                        return LLMResponse(
                            content=strategic_format_error(err_str),
                            finish_reason="error"
                        )
                    
            LiteLLMProvider.chat = _patched_chat

    def _patch_agent_loop_cleaning(self):
        """Patches AgentLoop to aggressively strip reasoning artifacts (<thought>, <think>, etc)."""
        from nanobot.agent.loop import AgentLoop
        if not hasattr(AgentLoop, "_orig_strip_think_strategic"):
            AgentLoop._orig_strip_think_strategic = AgentLoop._strip_think
            
            @staticmethod
            def _patched_strip_think(text: str | None) -> str | None:
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
            
            AgentLoop._strip_think = _patched_strip_think
