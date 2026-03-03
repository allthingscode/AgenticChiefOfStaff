from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path
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
        If no instance exists, it initializes the default (ChromaDB) implementation.
        """
        if cls._instance is None:
            from .vector_store import StrategicVectorStore
            from .config import load_strategic_context

            # Use provided root or derive it from strategic context
            if storage_root is None:
                _, _, storage_root = load_strategic_context()
            
            cls._instance = StrategicVectorStore(storage_root=storage_root, provider=provider)

            # Register with LifecycleManager for automatic cleanup
            from .lifecycle import lifecycle_manager
            lifecycle_manager.register_shutdown_hook(cls._instance.close)

            strategic_logger.debug(f"VectorStoreFactory initialized singleton store instance at {storage_root or 'default'}")

        # MANDATE: If a provider is passed to get_store, ensure the instance is using it.
        if provider:
            if hasattr(cls._instance, "provider"):
                # Track provider injection to diagnose BUG-022
                old_p = getattr(cls._instance, "provider", None)
                if old_p != provider:
                    cls._instance.provider = provider
                    p_type = type(provider).__name__
                    has_embed = hasattr(provider, "embed")
                    strategic_logger.debug(f"VectorStoreFactory injected provider: type={p_type}, has_embed={has_embed}")
            else:
                strategic_logger.warning("VectorStoreFactory: Store instance missing 'provider' attribute.")

        return cls._instance

    @classmethod
    def set_store(cls, store: VectorStoreInterface):
        """Allows injecting a mock store for testing."""
        cls._instance = store
