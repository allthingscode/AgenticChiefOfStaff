import os
import re
import asyncio
from .base import BasePatch
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
    Standalone wrapper for Google GenAI embedding with strategic logging.
    Used by StrategicVectorStore to bypass LiteLLM's sometimes inconsistent embedding routing.
    """
    try:
        from google import genai
        strategic_logger.info(f"GoogleGenAI embed: model={self.embedding_model}")
        client = genai.Client(api_key=self.api_key)
        result = await client.models.embed_content(
            model=self.embedding_model,
            contents=input_text
        )
        return [item.values for item in result.embeddings]
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
            self._patch_litellm_provider()
            self._patch_agent_loop_cleaning()
            return True
        except Exception as e:
            strategic_logger.error(f"Provider patch error: {e}")
            return False

    def _patch_litellm_provider(self):
        from nanobot.providers.litellm_provider import LiteLLMProvider
        if not hasattr(LiteLLMProvider, "_orig_chat_strategic"):
            LiteLLMProvider._orig_chat_strategic = LiteLLMProvider.chat
            
            async def _patched_chat(self, *args, **kwargs):
                model = kwargs.get("model") or (args[2] if len(args) > 2 else "unknown")
                strategic_log_provider_request("LiteLLM", model)
                
                # Execution with Strategic Retry & Error Interception
                try:
                    response = await self._orig_chat_strategic(*args, **kwargs)
                    
                    # Intercept error responses returned as successful calls (LiteLLM pattern)
                    if getattr(response, "finish_reason", None) == "error":
                        raw_content = str(response.content)
                        
                        # RETRY LOGIC: If it's a transient 500/503, try once more after a brief pause
                        if any(x in raw_content for x in ["500", "503", "InternalServerError", "ServiceUnavailable"]):
                            strategic_logger.warning(f"Transient error detected ({raw_content[:50]}). Initiating strategic retry...")
                            await asyncio.sleep(1.5)
                            response = await self._orig_chat_strategic(*args, **kwargs)
                            
                            # If still failing, format gracefully
                            if getattr(response, "finish_reason", None) == "error":
                                response.content = strategic_format_error(str(response.content))
                        else:
                            # Immediate formatting for non-retriable errors
                            response.content = strategic_format_error(raw_content)
                            
                    return response
                except Exception as e:
                    # Catch-all for unexpected provider crashes
                    strategic_logger.error(f"LiteLLM Fatal Crash: {e}")
                    from nanobot.providers.base import LLMResponse
                    return LLMResponse(
                        content=strategic_format_error(str(e)),
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
