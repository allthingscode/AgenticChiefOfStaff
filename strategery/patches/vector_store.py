from pathlib import Path
from typing import List, Dict, Any, Optional
from strategery.strategic_logger import get_logger
from .vsa import VectorStoreInterface

strategic_logger = get_logger()

class StrategicVectorStore(VectorStoreInterface):
    """
    Local-first vector store using ChromaDB.
    Handles semantic indexing and retrieval for Nanobot Strategic Edition.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(StrategicVectorStore, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, storage_root=None, provider=None):
        if getattr(self, "_initialized", False):
            # Allow updating the provider even if already initialized (e.g., if re-initialized with a different provider instance)
            if provider:
                self.provider = provider
            return
            
        # MANDATE: Storage root MUST be provided or resolved to home
        root = Path(storage_root or Path.home() / ".nanobot")
        self.storage_path = root / "workspace" / "memory" / "chroma"
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.provider = provider
        self.collection_name = "strategic_history"
        self._client = None
        self._collection = None
        self._initialized = True
        
        strategic_logger.info(f"Vector Store initialized at {self.storage_path}")

    async def _get_collection(self):
        if self._collection is None:
            try:
                import chromadb
                from chromadb.config import Settings
                
                self._client = chromadb.PersistentClient(
                    path=str(self.storage_path),
                    settings=Settings(anonymized_telemetry=False)
                )
                self._collection = self._client.get_or_create_collection(name=self.collection_name)
            except Exception as e:
                strategic_logger.error(f"Error initializing ChromaDB client: {e}", exc_info=True)
                raise
        return self._collection

    async def add_entry(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Vectorizes and adds a single entry to the store."""
        if not self.provider or not hasattr(self.provider, "embed"):
            p_type = type(self.provider).__name__ if self.provider else "NoneType"
            has_embed = hasattr(self.provider, "embed") if self.provider else False
            strategic_logger.error(f"Vector Store: No embedding provider available. (provider={p_type}, has_embed={has_embed})")
            return False

        try:
            collection = await self._get_collection()
            embeddings = await self.provider.embed(text)
            
            import uuid
            doc_id = str(uuid.uuid4())
            
            collection.add(
                ids=[doc_id],
                embeddings=embeddings,
                documents=[text],
                metadatas=[metadata or {}]
            )
            strategic_logger.debug(f"Vector Store: Added entry {doc_id}")
            return True
        except Exception as e:
            strategic_logger.error(f"Vector Store error during add: {e}")
            return False

    async def query(self, text: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """Queries the store for semantically similar entries."""
        if not self.provider or not hasattr(self.provider, "embed"):
            return []

        try:
            collection = await self._get_collection()
            embeddings = await self.provider.embed(text)
            
            results = collection.query(
                query_embeddings=embeddings,
                n_results=n_results
            )
            
            # Format results into list of dicts
            formatted = []
            if results and results['documents'] and len(results['documents']) > 0:
                for i in range(len(results['documents'][0])):
                    formatted.append({
                        "content": results['documents'][0][i],
                        "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                        "distance": results['distances'][0][i] if (results.get('distances') and len(results['distances']) > 0) else 0
                    })
            return formatted
        except Exception as e:
            strategic_logger.error(f"Vector Store error during query: {e}")
            return []

    async def close(self) -> None:
        """Gracefully closes any database connections."""
        if self._client:
            # ChromaDB's PersistentClient doesn't have an explicit close(), 
            # but we can clear our references to ensure GC can happen if needed.
            # Some versions use a heartbeat/telemetry that might need to be stopped.
            strategic_logger.info("Closing Vector Store connection...")
            self._collection = None
            self._client = None
            strategic_logger.debug("Vector Store connection references cleared.")
