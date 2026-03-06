
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
from pathlib import Path
import sys
import os

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from strategery.patches.vector_store import StrategicVectorStore
from strategery.patches.provider import strategic_litellm_embed

@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.api_key = "test-key"
    provider.embedding_model = "models/gemini-embedding-001"
    provider.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
    return provider

@pytest.fixture
def vector_store(mock_provider):
    # Reset singleton for testing
    StrategicVectorStore._instance = None
    store = StrategicVectorStore(storage_root="D:/Test_Storage", provider=mock_provider)
    return store

@pytest.mark.asyncio
async def test_vector_store_initialization(vector_store):
    """Verify vector store initialization and path setup."""
    # Use Path for platform-independent comparison
    expected_path = Path("D:/Test_Storage/workspace/memory/chroma")
    assert vector_store.storage_path == expected_path
    assert vector_store.collection_name == "strategic_history"

@pytest.mark.asyncio
async def test_vector_store_add_entry(vector_store, mock_provider):
    """Verify adding an entry to the vector store."""
    mock_collection = MagicMock()
    
    # Mock chromadb in sys.modules to avoid import on Python 3.14 (Pydantic v1 issue)
    mock_chroma = MagicMock()
    mock_config = MagicMock()
    with patch.dict("sys.modules", {"chromadb": mock_chroma, "chromadb.config": mock_config}):
        mock_client = mock_chroma.PersistentClient.return_value
        mock_client.get_or_create_collection.return_value = mock_collection
        
        success = await vector_store.add_entry("Test text", metadata={"source": "test"})
        
        assert success is True
        mock_provider.embed.assert_called_once_with("Test text")
        mock_collection.add.assert_called_once()
        args, kwargs = mock_collection.add.call_args
        assert kwargs["documents"] == ["Test text"]
        assert kwargs["metadatas"] == [{"source": "test"}]
        assert len(kwargs["embeddings"]) == 1

@pytest.mark.asyncio
async def test_vector_store_query(vector_store, mock_provider):
    """Verify querying the vector store."""
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "documents": [["Result 1", "Result 2"]],
        "metadatas": [[{"s": 1}, {"s": 2}]],
        "distances": [[0.1, 0.2]]
    }
    
    # Mock chromadb in sys.modules to avoid import on Python 3.14
    mock_chroma = MagicMock()
    mock_config = MagicMock()
    with patch.dict("sys.modules", {"chromadb": mock_chroma, "chromadb.config": mock_config}):
        mock_client = mock_chroma.PersistentClient.return_value
        mock_client.get_or_create_collection.return_value = mock_collection
        
        results = await vector_store.query("Search text", n_results=2)
        
        assert len(results) == 2
        assert results[0]["content"] == "Result 1"
        assert results[1]["content"] == "Result 2"
        mock_provider.embed.assert_called_once_with("Search text")

@pytest.mark.asyncio
async def test_strategic_litellm_embed_success():
    """Verify successful embedding using the modern Google GenAI library."""
    mock_self = MagicMock()
    mock_self.api_key = "test-key"
    mock_self.embedding_model = "models/gemini-embedding-001"
    
    mock_client = MagicMock()
    mock_result = MagicMock()
    # Mock return from client.aio.models.embed_content
    # item.values for each item in result.embeddings
    mock_item = MagicMock()
    mock_item.values = [0.1, 0.2, 0.3]
    mock_result.embeddings = [mock_item]
    mock_client.aio.models.embed_content = AsyncMock(return_value=mock_result)
    
    with patch("google.genai.Client", return_value=mock_client):
        embeddings = await strategic_litellm_embed(mock_self, "hello world")
        
        assert len(embeddings) == 1
        assert embeddings[0] == [0.1, 0.2, 0.3]
        mock_client.aio.models.embed_content.assert_called_once_with(
            model="models/gemini-embedding-001",
            contents="hello world"
        )

@pytest.mark.asyncio
async def test_strategic_litellm_embed_failure():
    """Verify graceful degradation on embedding failure."""
    mock_self = MagicMock()
    mock_self.api_key = "test-key"
    mock_self.embedding_model = "models/gemini-embedding-001"
    
    with patch("google.genai.Client", side_effect=Exception("API Error")):
        embeddings = await strategic_litellm_embed(mock_self, "hello world")
        assert embeddings == []
