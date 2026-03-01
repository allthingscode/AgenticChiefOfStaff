from loguru import logger
from . import BasePatch

class ProviderPatch(BasePatch):
    """Handles logging and routing patches for LLM providers."""
    
    @property
    def name(self) -> str:
        return "Provider Logging & Routing"

    def apply(self, config_data: dict) -> bool:
        try:
            self._patch_litellm()
            self._patch_custom()
            self._patch_codex()
            return True
        except Exception as e:
            print(f"[Launcher] Provider patch error: {e}")
            return False

    def _patch_litellm(self):
        from nanobot.providers.litellm_provider import LiteLLMProvider
        if not hasattr(LiteLLMProvider, "_orig_chat_strategic"):
            LiteLLMProvider._orig_chat_strategic = LiteLLMProvider.chat
            async def _patched_litellm_chat(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7, reasoning_effort=None, **kwargs):
                target_model = model or self.default_model
                logger.info("[Strategic] LiteLLM request: model={}", target_model)
                return await self._orig_chat_strategic(messages, tools=tools, model=model, max_tokens=max_tokens, temperature=temperature, reasoning_effort=reasoning_effort, **kwargs)
            LiteLLMProvider.chat = _patched_litellm_chat

    def _patch_custom(self):
        from nanobot.providers.custom_provider import CustomProvider
        if not hasattr(CustomProvider, "_orig_chat_strategic"):
            CustomProvider._orig_chat_strategic = CustomProvider.chat
            async def _patched_custom_chat(self, *args, **kwargs):
                model = kwargs.get("model") or self.default_model
                logger.info("[Strategic] CustomProvider request: model={}", model)
                return await self._orig_chat_strategic(*args, **kwargs)
            CustomProvider.chat = _patched_custom_chat

    def _patch_codex(self):
        from nanobot.providers.openai_codex_provider import OpenAICodexProvider
        if not hasattr(OpenAICodexProvider, "_orig_chat_strategic"):
            OpenAICodexProvider._orig_chat_strategic = OpenAICodexProvider.chat
            async def _patched_codex_chat(self, *args, **kwargs):
                model = kwargs.get("model") or self.default_model
                logger.info("[Strategic] Codex request: model={}", model)
                return await self._orig_chat_strategic(*args, **kwargs)
            OpenAICodexProvider.chat = _patched_codex_chat
