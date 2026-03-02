from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from strategery.strategic_logger import strategic_logger

class VectorStoreInterface(ABC):
    """
    Abstract interface for vector storage and retrieval.
    Decouples strategic logic from specific database implementations.
    """
    
    @abstractmethod
    async def add_entry(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Vectorizes and adds a single entry to the store."""
        pass

    @abstractmethod
    async def query(self, text: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """Queries the store for semantically similar entries."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Gracefully closes any database connections."""
        pass

class VectorStoreFactory:
    """
    Factory to manage the singleton instance of the active vector store.
    """
    _instance: Optional[VectorStoreInterface] = None

    @classmethod
    def get_store(cls, provider=None, storage_root=None) -> VectorStoreInterface:
        """
        Returns the active vector store instance.
        If no instance exists, it initializes the default (ChromaDB) implementation.
        """
        if cls._instance is None:
            # For now, we default to our ChromaDB implementation
            from .vector_store import StrategicVectorStore
            from . import registry
            
            # Use provided root or fallback to the globally resolved one
            root = storage_root or registry.storage_root
            cls._instance = StrategicVectorStore(storage_root=root, provider=provider)
            
            # Register with LifecycleManager for automatic cleanup
            from .lifecycle import lifecycle_manager
            lifecycle_manager.register_shutdown_hook(cls._instance.close)
            
            strategic_logger.debug(f"VectorStoreFactory initialized singleton store instance at {root or 'default'}")
            
        return cls._instance

    @classmethod
    def set_store(cls, store: VectorStoreInterface):
        """Allows injecting a mock store for testing."""
        cls._instance = store
