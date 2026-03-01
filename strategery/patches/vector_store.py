import os
import asyncio
from pathlib import Path
from loguru import logger

class StrategicVectorStore:
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
        if self._initialized:
            return
            
        self.storage_path = Path(storage_root or "D:/Nanobot_Storage") / "workspace" / "memory" / "chroma"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.provider = provider
        self.collection_name = "strategic_history"
        self._client = None
        self._collection = None
        self._initialized = True
        
        logger.info("[Strategic] Vector Store initialized at {}", self.storage_path)

    async def _get_collection(self):
        if self._collection is None:
            import chromadb
            from chromadb.config import Settings
            
            self._client = chromadb.PersistentClient(
                path=str(self.storage_path),
                settings=Settings(anonymized_telemetry=False)
            )
            self._collection = self._client.get_or_create_collection(name=self.collection_name)
        return self._collection

    async def add_entry(self, text, metadata=None):
        """Vectorizes and adds a single entry to the store."""
        if not self.provider or not hasattr(self.provider, "embed"):
            logger.error("[Strategic] Vector Store: No embedding provider available.")
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
            logger.debug("[Strategic] Vector Store: Added entry {}", doc_id)
            return True
        except Exception as e:
            logger.error("[Strategic] Vector Store error during add: {}", e)
            return False

    async def query(self, text, n_results=3):
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
            if results and results['documents']:
                for i in range(len(results['documents'][0])):
                    formatted.append({
                        "content": results['documents'][0][i],
                        "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                        "distance": results['distances'][0][i] if results['distances'] else 0
                    })
            return formatted
        except Exception as e:
            logger.error("[Strategic] Vector Store error during query: {}", e)
            return []
