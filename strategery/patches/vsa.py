from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from strategery.strategic_logger import strategic_logger

class VectorStoreInterface(ABC):
    """
    Abstract interface for vector memory storage.
    Enables swapping implementations (e.g., ChromaDB vs in-memory) without core changes.
    """
    @abstractmethod
    async def add_entry(self, content: str, metadata: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    async def query(self, text: str, n_results: int = 3) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def close(self):
        pass

class VectorStoreFactory:
    """
    Singleton factory for accessing the strategic vector store.
    Handles lazy initialization and implementation selection.
    """
    _instance: Optional[VectorStoreInterface] = None

    @classmethod
    def get_store(cls, provider=None, storage_root=None) -> VectorStoreInterface:
        """
        Returns the active vector store instance.
        If no instance exists, it initializes the default (Hybrid: SQLite + ChromaDB) implementation.
        """
        # MANDATE (BUG-165): Ensure the provider instance has the strategic 'embed' patch
        # before we do anything else.
        if provider and not hasattr(provider, "embed"):
            try:
                from nanobot.providers.base import LLMProvider
                if isinstance(provider, LLMProvider):
                    from .provider import strategic_litellm_embed
                    provider.embed = strategic_litellm_embed.__get__(provider, type(provider))
                    provider.embedding_model = "models/gemini-embedding-001"
                    strategic_logger.debug(f"VectorStoreFactory: Late-patched provider ({type(provider).__name__}) with strategic embed.")
            except Exception as e:
                strategic_logger.error(f"VectorStoreFactory: Failed to late-patch provider: {e}")

        if cls._instance is None:
            from .hybrid_store import StrategicHybridStore
            from .config import load_strategic_context

            # Use provided root or derive it from strategic context
            if storage_root is None:
                _, _, storage_root = load_strategic_context()

            cls._instance = StrategicHybridStore(storage_root=storage_root, provider=provider)

            # Register with LifecycleManager for automatic cleanup
            from .lifecycle import lifecycle_manager
            lifecycle_manager.register_shutdown_hook(cls._instance.close)
            p_type = type(provider).__name__ if provider else "NoneType"
            has_embed = hasattr(provider, "embed") if provider else False
            strategic_logger.debug(f"VectorStoreFactory: Initialized singleton with provider type={p_type}, has_embed={has_embed}")

        # MANDATE: If a provider is passed to get_store, ensure the instance is using it.
        if provider:
            if hasattr(cls._instance, "provider"):
                # Track provider injection to diagnose BUG-022 / BUG-030
                old_p = getattr(cls._instance, "provider", None)
                if old_p != provider:
                    cls._instance.provider = provider
                    p_type = type(provider).__name__
                    has_embed = hasattr(provider, "embed")
                    strategic_logger.debug(f"VectorStoreFactory injected provider: type={p_type}, has_embed={has_embed}")
                else:
                    # Even if it's the same instance, log if it's missing the embed method
                    if not hasattr(cls._instance.provider, "embed"):
                        p_type = type(cls._instance.provider).__name__
                        strategic_logger.warning(f"VectorStoreFactory: Current provider ({p_type}) is MISSING 'embed' method!")
            else:
                strategic_logger.warning("VectorStoreFactory: Store instance missing 'provider' attribute.")
        elif cls._instance and not getattr(cls._instance, "provider", None):
             strategic_logger.warning("VectorStoreFactory: get_store() called with no provider, and instance has NONE.")

        return cls._instance

    @classmethod
    def set_store(cls, store: VectorStoreInterface):
        """Allows injecting a mock store for testing."""
        cls._instance = store
