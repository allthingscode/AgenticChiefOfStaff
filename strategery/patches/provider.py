from loguru import logger
from . import BasePatch

def strategic_log_provider_request(provider_name, model, action="request"):
    """Logs the provider activity in a standardized strategic format."""
    logger.info("[Strategic] {} {}: model={}", provider_name, action, model)
async def strategic_litellm_embed(self, input_text, model=None):
    """
    Strategic embedding implementation for LiteLLMProvider.
    Uses the modern google-genai library with confirmed authorized model.
    """
    from google import genai
    from loguru import logger

    # MANDATE: Use the EXACT confirmed model from discovery
    target_model = model or getattr(self, "embedding_model", "models/gemini-embedding-001")
    
    try:
        strategic_log_provider_request("GoogleGenAI", target_model, action="embed")
        
        # Initialize client with the API key
        client = genai.Client(api_key=self.api_key)
        
        # Determine if we have a single string or multiple
        texts = [input_text] if isinstance(input_text, str) else input_text
        
        # Perform embedding
        result = client.models.embed_content(
            model=target_model,
            contents=texts
        )
        
        # Extract embeddings
        embeddings = [item.values for item in result.embeddings]
        return embeddings
        
    except Exception as e:
        logger.error("[Strategic] Modern Google Embedding failure ({}): {}", target_model, e)
        return []
class ProviderPatch(BasePatch):
    """Handles logging, routing, and embedding patches for LLM providers."""

    @property
    def name(self) -> str:
        return "Provider Logging & Routing"

    def apply(self, config_data: dict) -> bool:
        try:
            self._patch_litellm(config_data)
            self._patch_custom()
            self._patch_codex()
            return True
        except Exception as e:
            print(f"[Launcher] Provider patch error: {e}")
            return False

    def _patch_litellm(self, config_data):
        from nanobot.providers.litellm_provider import LiteLLMProvider

        # 1. Patch Chat
        if not hasattr(LiteLLMProvider, "_orig_chat_strategic"):
            LiteLLMProvider._orig_chat_strategic = LiteLLMProvider.chat
            async def _patched_litellm_chat(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7, reasoning_effort=None, **kwargs):
                target_model = model or self.default_model
                strategic_log_provider_request("LiteLLM", target_model)
                return await self._orig_chat_strategic(messages, tools=tools, model=model, max_tokens=max_tokens, temperature=temperature, reasoning_effort=reasoning_effort, **kwargs)
            LiteLLMProvider.chat = _patched_litellm_chat

        # 2. Patch Embed (New strategic functionality)
        if not hasattr(LiteLLMProvider, "embed"):
            # Set default embedding model from config if present
            embedding_model = config_data.get("strategic_edition", {}).get("embedding_model", "models/gemini-embedding-001")
            LiteLLMProvider.embedding_model = embedding_model

            # We bind the standalone function as a method
            LiteLLMProvider.embed = strategic_litellm_embed

    def _patch_custom(self):
        from nanobot.providers.custom_provider import CustomProvider
        if not hasattr(CustomProvider, "_orig_chat_strategic"):
            CustomProvider._orig_chat_strategic = CustomProvider.chat
            async def _patched_custom_chat(self, *args, **kwargs):
                model = kwargs.get("model") or self.default_model
                strategic_log_provider_request("CustomProvider", model)
                return await self._orig_chat_strategic(*args, **kwargs)
            CustomProvider.chat = _patched_custom_chat

    def _patch_codex(self):
        from nanobot.providers.openai_codex_provider import OpenAICodexProvider
        if not hasattr(OpenAICodexProvider, "_orig_chat_strategic"):
            OpenAICodexProvider._orig_chat_strategic = OpenAICodexProvider.chat
            async def _patched_codex_chat(self, *args, **kwargs):
                model = kwargs.get("model") or self.default_model
                strategic_log_provider_request("Codex", model)
                return await self._orig_chat_strategic(*args, **kwargs)
            OpenAICodexProvider.chat = _patched_codex_chat
