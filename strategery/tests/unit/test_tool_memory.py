import pytest
from unittest.mock import AsyncMock, patch
from strategery.tools.strategic_memory import SearchMemoryTool

@pytest.mark.asyncio
async def test_search_memory_tool_execution():
    """Verify that SearchMemoryTool correctly queries the VectorStoreFactory."""
    tool = SearchMemoryTool()
    
    # Mock data
    mock_results = [
        {
            "content": "Past decision: Use PostgreSQL.",
            "metadata": {"timestamp": "2025-01-01", "source": "consolidation"},
            "distance": 0.1
        },
        {
            "content": "Project context: Strategic Edition is modular.",
            "metadata": {"timestamp": "2025-02-01", "source": "daily_journal"},
            "distance": 0.3
        }
    ]

    with patch("strategery.patches.vsa.VectorStoreFactory.get_store") as mock_get_store:
        mock_store = AsyncMock()
        mock_store.query.return_value = mock_results
        mock_get_store.return_value = mock_store

        # Execute tool
        result = await tool.execute(query="database decision", n_results=2)

        # Verifications
        mock_store.query.assert_called_once_with("database decision", n_results=2)
        assert "Found 2 relevant memories" in result
        assert "Use PostgreSQL" in result
        assert "Strategic Edition is modular" in result
        assert "Relevance: 0.90" in result  # 1.0 - 0.1
        assert "Relevance: 0.70" in result  # 1.0 - 0.3

@pytest.mark.asyncio
async def test_search_memory_tool_no_results():
    """Verify handling of empty results."""
    tool = SearchMemoryTool()

    with patch("strategery.patches.vsa.VectorStoreFactory.get_store") as mock_get_store:
        mock_store = AsyncMock()
        mock_store.query.return_value = []
        mock_get_store.return_value = mock_store

        result = await tool.execute(query="nonexistent query")

        assert "No relevant memories found" in result

@pytest.mark.asyncio
async def test_search_memory_tool_error():
    """Verify error handling."""
    tool = SearchMemoryTool()

    with patch("strategery.patches.vsa.VectorStoreFactory.get_store") as mock_get_store:
        mock_store = AsyncMock()
        mock_store.query.side_effect = Exception("ChromaDB Failure")
        mock_get_store.return_value = mock_store

        result = await tool.execute(query="test query")

        assert "Error querying memory" in result
        assert "ChromaDB Failure" in result
