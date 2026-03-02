import pytest
import asyncio
from typing import List, Dict, Any, Optional
from strategery.patches.vsa import VectorStoreInterface, VectorStoreFactory

class MockVectorStore(VectorStoreInterface):
    def __init__(self):
        self.entries = []
        self.closed = False

    async def add_entry(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        self.entries.append({"text": text, "metadata": metadata})
        return True

    async def query(self, text: str, n_results: int = 3) -> List[Dict[str, Any]]:
        return [{"content": "mock result", "metadata": {}, "distance": 0.1}]

    async def close(self) -> None:
        self.closed = True

@pytest.mark.asyncio
async def test_vsa_factory_injection():
    """Verify that we can inject a mock store into the factory."""
    mock_store = MockVectorStore()
    VectorStoreFactory.set_store(mock_store)
    
    retrieved_store = VectorStoreFactory.get_store()
    assert retrieved_store is mock_store
    
    success = await retrieved_store.add_entry("test text")
    assert success is True
    assert len(mock_store.entries) == 1
    
    results = await retrieved_store.query("search")
    assert len(results) == 1
    assert results[0]["content"] == "mock result"

@pytest.mark.asyncio
async def test_vsa_interface_compliance():
    """Verify that the real store complies with the interface."""
    # This just checks that it can be instantiated as a VectorStoreInterface
    from strategery.patches.vector_store import StrategicVectorStore
    store = StrategicVectorStore(storage_root="./test_storage")
    assert isinstance(store, VectorStoreInterface)
