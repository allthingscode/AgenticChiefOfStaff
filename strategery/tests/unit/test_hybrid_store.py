import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from strategery.patches.hybrid_store import StrategicHybridStore

@pytest.mark.asyncio
async def test_hybrid_store_basic_operations(tmp_path):
    """Verify that HybridStore correctly syncs to SQLite and Vector Store."""
    mock_provider = MagicMock()
    mock_provider.embed = AsyncMock(return_value=[0.1]*1536)
    
    # 1. Initialize
    with patch("strategery.patches.vector_store.StrategicVectorStore.__init__", return_value=None):
        store = StrategicHybridStore(storage_root=tmp_path, provider=mock_provider)
        
        # Manually mock the vector store's add_entry and query
        store.vector_store.add_entry = AsyncMock(return_value=True)
        store.vector_store.query = AsyncMock(return_value=[
            {"content": "Semantic Result", "metadata": {}, "distance": 0.5}
        ])
        
        # 2. Add Entry
        text = "BUG-042: SQLite FTS5 implementation completed."
        metadata = {"source": "unit_test", "timestamp": "2026-03-04T12:00:00"}
        
        success = await store.add_entry(text, metadata)
        assert success is True
        
        # Verify SQLite insertion
        cursor = store._db_conn.cursor()
        cursor.execute("SELECT content FROM memory_fts")
        row = cursor.fetchone()
        assert row[0] == text
        
        # 3. Query - Keyword Priority
        # We query for the exact ID "BUG-042"
        results = await store.query("BUG-042", n_results=5)
        
        assert len(results) >= 1
        # Keyword result should be present and have 'type': 'keyword'
        keyword_results = [r for r in results if r.get("type") == "keyword"]
        assert len(keyword_results) == 1
        assert "BUG-042" in keyword_results[0]["content"]
        
        # 4. Query - Semantic Fallback
        results_semantic = await store.query("database implementation", n_results=5)
        assert any("Semantic Result" in r["content"] for r in results_semantic)

@pytest.mark.asyncio
async def test_hybrid_store_deduplication(tmp_path):
    """Verify that redundant results between Keyword and Semantic are merged."""
    mock_provider = MagicMock()
    
    with patch("strategery.patches.vector_store.StrategicVectorStore.__init__", return_value=None):
        store = StrategicHybridStore(storage_root=tmp_path, provider=mock_provider)
        
        # Add a specific entry to SQLite
        text = "Unique Keyword Fact"
        await store.add_entry(text, {"source": "test"})
        
        # Mock Vector Store to return the SAME content
        store.vector_store.query = AsyncMock(return_value=[
            {"content": "Unique Keyword Fact", "metadata": {"source": "test"}, "distance": 0.1}
        ])
        
        results = await store.query("Unique Keyword", n_results=5)
        
        # Should only have ONE result because of deduplication
        assert len(results) == 1
        # The keyword result (prioritized) should be the one we kept
        assert results[0].get("type") == "keyword"

@pytest.mark.asyncio
async def test_hybrid_store_empty_query(tmp_path):
    """Verify handling of queries with no matches."""
    mock_provider = MagicMock()
    
    with patch("strategery.patches.vector_store.StrategicVectorStore.__init__", return_value=None):
        store = StrategicHybridStore(storage_root=tmp_path, provider=mock_provider)
        store.vector_store.query = AsyncMock(return_value=[])
        
        results = await store.query("Something that exists nowhere", n_results=5)
        assert results == []
