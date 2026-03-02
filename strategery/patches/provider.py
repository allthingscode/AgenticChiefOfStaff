import os
import re
from . import BasePatch
from strategery.strategic_logger import strategic_logger

def strategic_log_provider_request(provider_name, model):
    """Logs LLM requests at the INFO level for strategic visibility."""
    strategic_logger.info(f"{provider_name} request: model={model}")

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
    """Handles provider-level logging, routing, and response cleaning."""
    
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
                return await self._orig_chat_strategic(*args, **kwargs)
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
                
                # 2. STRATEGIC: Strip trailing reasoning markers like "thought." or "thought:"
                res = re.sub(r"\s+thought[\.:]?$", "", res, flags=re.IGNORECASE)
                
                # 3. STRATEGIC: Strip lingering lone opening/closing tags if any survived
                res = re.sub(r"</?(think|thought)>", "", res, flags=re.IGNORECASE).strip()
                
                return res or None
            
            AgentLoop._strip_think = _patched_strip_think
