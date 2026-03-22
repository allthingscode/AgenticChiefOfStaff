import sqlite3
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from strategery.strategic_logger import get_logger
from .vsa import VectorStoreInterface

strategic_logger = get_logger()

class StrategicHybridStore(VectorStoreInterface):
    """
    Hybrid Memory Store combining Semantic (Vector) and Keyword (FTS5) search.
    Syncs entries between ChromaDB and SQLite.
    """
    _instance = None

    def __new__(cls, storage_root=None, provider=None):
        # MANDATE: If a new storage_root is provided (as in unit tests), 
        # we MUST force re-initialization even if an instance exists.
        if cls._instance is None:
            cls._instance = super(StrategicHybridStore, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, storage_root=None, provider=None):
        # BUG-FIX: Re-initialize if storage_root changes (prevents test pollution)
        root = Path(storage_root or Path.home() / ".nanobot")
        target_sqlite_path = root / "workspace" / "memory" / "keyword_index.db"
        
        if getattr(self, "_initialized", False):
            if hasattr(self, "sqlite_path") and self.sqlite_path == target_sqlite_path:
                if provider: self.provider = provider
                return
            # Path changed, close existing connection
            if hasattr(self, "_db_conn") and self._db_conn:
                self._db_conn.close()
                self._db_conn = None

        self.memory_dir = root / "workspace" / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # SQLite Path for FTS
        self.sqlite_path = target_sqlite_path
        
        # Initialize Vector Store (Lazy)
        from .vector_store import StrategicVectorStore
        self.vector_store = StrategicVectorStore(storage_root=storage_root, provider=provider)
        
        self.provider = provider
        self._db_conn = None
        self._initialized = True
        
        # Setup SQLite Schema
        self._init_sqlite()
        strategic_logger.info(f"Hybrid Store initialized. SQLite: {self.sqlite_path}")

    def _init_sqlite(self):
        """Initializes the SQLite database with FTS5 virtual table."""
        try:
            conn = sqlite3.connect(self.sqlite_path)
            cursor = conn.cursor()
            
            # Metadata Table (Relational)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory_metadata (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    source TEXT,
                    raw_metadata TEXT
                )
            """)
            
            # FTS5 Virtual Table (Searchable)
            # content is unindexed in the metadata table but indexed here
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    id UNINDEXED,
                    content,
                    tokenize='porter unicode61'
                )
            """)
            conn.commit()
            self._db_conn = conn
        except Exception as e:
            strategic_logger.error(f"Hybrid Store: SQLite init failed: {e}")

    async def add_entry(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Adds entry to both Vector Store and SQLite FTS."""
        import uuid
        doc_id = str(uuid.uuid4())
        
        # 1. Add to Vector Store
        # Note: VectorStore.add_entry generates its own UUID, we should sync them if possible.
        # For simplicity in this patch, we'll let VectorStore do its thing, 
        # but we use OUR doc_id for SQLite to ensure we can track it.
        # Actually, let's modify the VectorStore to accept an ID? 
        # No, Zero Core Pollution - let's just use the same text/metadata.
        
        v_success = await self.vector_store.add_entry(text, metadata)
        
        # 2. Add to SQLite
        try:
            ts = metadata.get("timestamp") or datetime.now().isoformat()
            source = metadata.get("source") or "unknown"
            meta_json = json.dumps(metadata or {})
            
            cursor = self._db_conn.cursor()
            cursor.execute(
                "INSERT INTO memory_metadata (id, timestamp, source, raw_metadata) VALUES (?, ?, ?, ?)",
                (doc_id, ts, source, meta_json)
            )
            cursor.execute(
                "INSERT INTO memory_fts (id, content) VALUES (?, ?)",
                (doc_id, text)
            )
            self._db_conn.commit()
            return v_success
        except Exception as e:
            strategic_logger.error(f"Hybrid Store: SQLite add failed: {e}")
            return False

    async def query(self, text: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Performs a Hybrid Search (Semantic + Keyword)."""
        # 1. Semantic Query
        v_results = await self.vector_store.query(text, n_results=n_results)
        
        # 2. Keyword Query (FTS5)
        k_results = self._keyword_search(text, n_results=n_results)
        
        # 3. Merge & Deduplicate
        # Simple Merge: Keyword results prioritized for exact matches, then semantic.
        merged = []
        seen_content = set()
        
        # Add keyword results first (high precision)
        for res in k_results:
            content = res["content"]
            if content not in seen_content:
                merged.append(res)
                seen_content.add(content)
                
        # Add semantic results (high recall)
        for res in v_results:
            content = res["content"]
            if content not in seen_content:
                merged.append(res)
                seen_content.add(content)
                
        return merged[:n_results]

    def _keyword_search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Internal SQLite FTS5 search."""
        try:
            cursor = self._db_conn.cursor()
            
            # Clean query for FTS5
            # MANDATE: Wrap query in double quotes to handle IDs with hyphens (e.g. BUG-042)
            # as FTS5 treats hyphen as a NOT operator if not quoted.
            safe_query = f'"{query.replace('"', '""')}"'
            
            # Clean query for FTS5 (escape special chars if needed, but porter helps)
            # We use the BM25 ranking built into FTS5
            sql = """
                SELECT f.id, f.content, m.timestamp, m.source, m.raw_metadata, rank
                FROM memory_fts f
                JOIN memory_metadata m ON f.id = m.id
                WHERE memory_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """
            
            cursor.execute(sql, (safe_query, n_results))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "content": row[1],
                    "metadata": json.loads(row[4]) if row[4] else {},
                    "distance": row[5], # BM25 Rank (lower is better in FTS5 rank)
                    "type": "keyword"
                })
            return results
        except Exception as e:
            strategic_logger.error(f"Hybrid Store: Keyword search failed: {e}")
            return []

    async def close(self) -> None:
        """Closes connections."""
        if self._db_conn:
            self._db_conn.close()
            self._db_conn = None
        await self.vector_store.close()
