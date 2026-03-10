import asyncio
from typing import Any, List
from .base import BasePatch, PatchResult, PatchContext
from strategery.strategic_logger import strategic_logger
from strategery.logic import provider_logic

async def strategic_litellm_embed(self, input_text):
    """Bridge to the strategic embedding logic."""
    model_name = getattr(self, "embedding_model", "models/gemini-embedding-001")
    return await provider_logic.run_strategic_embedding(self.api_key, model_name, input_text)

class ProviderPatch(BasePatch):
    """Thin Bridge for provider-level logging, routing, and error interception."""
    
    @property
    def name(self) -> str:
        return "Provider Logging & Routing"

    @property
    def required_symbols(self) -> List[str]:
        return [
            "nanobot.providers.base.LLMProvider",
            "nanobot.providers.litellm_provider.LiteLLMProvider",
            "nanobot.agent.loop.AgentLoop._strip_think"
        ]

    def apply(self, context: PatchContext) -> PatchResult:
        result = PatchResult(patch_name=self.name, success=True)
        try:
            self._patch_base_provider()
            result.affected_symbols.append("LLMProvider.embed")

            self._patch_litellm_provider()
            result.affected_symbols.extend(["LiteLLMProvider.chat", "LiteLLMProvider.embed"])

            self._patch_litellm_parsing()
            result.affected_symbols.append("LiteLLMProvider._parse_response")

            self._patch_azure_openai_provider()
            # Note: Azure might not be installed, so we check affected_symbols inside the helper or just ignore
            
            self._patch_agent_loop_cleaning()
            result.affected_symbols.append("AgentLoop._strip_think")

            return result
        except Exception as e:
            import traceback
            result.success = False
            result.error_msg = str(e)
            result.traceback = traceback.format_exc()
            strategic_logger.error(f"Provider patch error: {e}")
            return result

    def _patch_litellm_parsing(self):
        """Patches LiteLLMProvider._parse_response to prevent IndexError on empty choices."""
        from nanobot.providers.litellm_provider import LiteLLMProvider
        if not hasattr(LiteLLMProvider, "_orig_parse_response_strategic"):
            LiteLLMProvider._orig_parse_response_strategic = LiteLLMProvider._parse_response
            
            def _patched_parse_response(self, response: Any):
                # Use strategic logic to ensure choices are present
                safe_response = provider_logic.safe_parse_litellm_response(response)
                return self._orig_parse_response_strategic(safe_response)
            
            LiteLLMProvider._parse_response = _patched_parse_response

    def _patch_azure_openai_provider(self):
        try:
            from nanobot.providers.azure_openai_provider import AzureOpenAIProvider
        except ImportError:
            return

        if not hasattr(AzureOpenAIProvider, "_orig_chat_strategic"):
            AzureOpenAIProvider._orig_chat_strategic = AzureOpenAIProvider.chat
            
            async def _patched_chat(self, *args, **kwargs):
                model = kwargs.get("model") or (args[2] if len(args) > 2 else self.default_model)
                strategic_logger.info(provider_logic.format_provider_log("AzureOpenAI", model))
                
                max_retries = 3
                retry_delay = 2.0
                
                for attempt in range(max_retries):
                    try:
                        response = await self._orig_chat_strategic(*args, **kwargs)
                        if getattr(response, "finish_reason", None) == "error":
                            raw_content = str(response.content)
                            is_transient = any(x in raw_content for x in ["500", "503", "504", "InternalServerError", "ServiceUnavailable", "RateLimitError", "429", "timeout"])
                            if is_transient and attempt < max_retries - 1:
                                await asyncio.sleep(retry_delay)
                                retry_delay *= 2
                                continue
                            response.content = provider_logic.format_strategic_error(raw_content)
                        return response
                    except Exception as e:
                        err_str = str(e)
                        is_transient = any(x in err_str for x in ["500", "503", "InternalServerError", "ServiceUnavailable", "RateLimit", "429", "Timeout"])
                        if is_transient and attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2
                            continue
                        from nanobot.providers.base import LLMResponse
                        return LLMResponse(content=provider_logic.format_strategic_error(err_str), finish_reason="error")
            
            AzureOpenAIProvider.chat = _patched_chat

    def _patch_base_provider(self):
        from nanobot.providers.base import LLMProvider
        # Mandate (BUG-165): Patch the base class so all instances (LiteLLM, Azure, etc) 
        # inherit the strategic embed logic by default.
        if not hasattr(LLMProvider, "embed"):
            LLMProvider.embed = strategic_litellm_embed
            LLMProvider.embedding_model = "models/gemini-embedding-001"
            strategic_logger.debug("Patched LLMProvider base class with strategic embed.")

    def _patch_litellm_provider(self):
        from nanobot.providers.litellm_provider import LiteLLMProvider
        
        if not hasattr(LiteLLMProvider, "embed"):
            LiteLLMProvider.embed = strategic_litellm_embed
            LiteLLMProvider.embedding_model = "models/gemini-embedding-001"

        if not hasattr(LiteLLMProvider, "_orig_chat_strategic"):
            LiteLLMProvider._orig_chat_strategic = LiteLLMProvider.chat
            
            async def _patched_chat(self, *args, **kwargs):
                model = kwargs.get("model") or (args[1] if len(args) > 1 else (args[2] if len(args) > 2 else "unknown"))
                strategic_logger.info(provider_logic.format_provider_log("LiteLLM", model))
                
                max_retries = 3
                retry_delay = 2.0
                
                for attempt in range(max_retries):
                    try:
                        response = await self._orig_chat_strategic(*args, **kwargs)
                        if getattr(response, "finish_reason", None) == "error":
                            raw_content = str(response.content)
                            is_transient = any(x in raw_content for x in ["500", "503", "504", "InternalServerError", "ServiceUnavailable", "RateLimitError", "429", "timeout"])
                            if is_transient and attempt < max_retries - 1:
                                await asyncio.sleep(retry_delay)
                                retry_delay *= 2
                                continue
                            response.content = provider_logic.format_strategic_error(raw_content)
                        return response
                    except Exception as e:
                        err_str = str(e)
                        is_transient = any(x in err_str for x in ["500", "503", "InternalServerError", "ServiceUnavailable", "RateLimit", "429", "Timeout"])
                        if is_transient and attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2
                            continue
                        from nanobot.providers.base import LLMResponse
                        return LLMResponse(content=provider_logic.format_strategic_error(err_str), finish_reason="error")
            
            LiteLLMProvider.chat = _patched_chat

    def _patch_agent_loop_cleaning(self):
        """Patches AgentLoop to aggressively strip reasoning artifacts."""
        from nanobot.agent.loop import AgentLoop
        if not hasattr(AgentLoop, "_orig_strip_think_strategic"):
            AgentLoop._orig_strip_think_strategic = AgentLoop._strip_think
            
            @staticmethod
            def _patched_strip_think(text: str | None) -> str | None:
                return provider_logic.strip_reasoning_artifacts(text)
            
            AgentLoop._strip_think = _patched_strip_think
