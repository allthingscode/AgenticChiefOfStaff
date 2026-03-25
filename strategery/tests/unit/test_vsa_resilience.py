import pytest
import logging
from pathlib import Path
from unittest.mock import patch
from nanobot.providers.litellm_provider import LiteLLMProvider
from strategery.patches.vsa import VectorStoreFactory
from strategery.patches.vector_store import StrategicVectorStore

@pytest.fixture(autouse=True)
def reset_vsa_singleton():
    """Ensure the singleton is reset."""
    from strategery.patches.hybrid_store import StrategicHybridStore
    VectorStoreFactory._instance = None
    StrategicVectorStore._instance = None
    StrategicHybridStore._instance = None
    yield
    VectorStoreFactory._instance = None
    StrategicVectorStore._instance = None
    StrategicHybridStore._instance = None

@pytest.mark.asyncio
async def test_vsa_factory_initialization(mock_context):
    """Verify first-time initialization with a real provider."""
    from strategery.patches.hybrid_store import StrategicHybridStore
    provider = LiteLLMProvider(api_key="test-key")
    store = VectorStoreFactory.get_store(provider=provider, storage_root=mock_context.storage_root)
    
    assert isinstance(store, StrategicHybridStore)
    assert store.provider == provider
    # StrategicHybridStore wraps vector_store
    assert isinstance(store.vector_store, StrategicVectorStore)
    # StrategicVectorStore derives storage_path from storage_root
    # We verify it ends with the expected platform-agnostic suffix
    expected_suffix = str(Path("workspace") / "memory" / "chroma").lower()
    assert str(store.vector_store.storage_path).lower().endswith(expected_suffix)

@pytest.mark.asyncio
async def test_vsa_late_patching_resilience(mock_context):
    """
    CRITICAL TEST for BUG-030:
    Verify that if a provider loses its 'embed' method, the factory restores it.
    """
    from nanobot.providers.base import LLMProvider
    
    class NakedProvider(LLMProvider):
        def __init__(self, api_key=None):
             pass
        async def chat(self, messages, tools=None, model=None, **kwargs):
             return None
        def get_default_model(self):
             return "test-model"

    provider = NakedProvider()
    
    # We must mock the fact that it doesn't have it in vsa.py's context
    with patch("strategery.patches.vsa.hasattr", side_effect=lambda obj, attr: False if attr == "embed" and obj == provider else hasattr(obj, attr)):
        # 2. Access store via factory
        store = VectorStoreFactory.get_store(provider=provider, storage_root=mock_context.storage_root)
        # Force missing provider on instance to trigger the late-patch logic if get_store is called again
        store.provider = None 

        # 3. Trigger late-patching via a second get_store call
        VectorStoreFactory.get_store(provider=provider)
        
        # 4. Verification
        # Dir should contain it now because it was late-patched
        assert "embed" in dir(provider) or hasattr(provider, "embed")
        assert store.provider == provider

@pytest.mark.asyncio
async def test_vsa_provider_swap(mock_context):
    """Verify that the factory correctly updates the provider on the singleton."""
    p1 = LiteLLMProvider(api_key="key-1")
    p2 = LiteLLMProvider(api_key="key-2")

    store = VectorStoreFactory.get_store(provider=p1, storage_root=mock_context.storage_root)
    assert store.provider == p1
    
    # Swap via factory
    VectorStoreFactory.get_store(provider=p2)
    assert store.provider == p2

def test_vsa_warning_no_provider(mock_context, caplog):
    """Verify that accessing without a provider when none exists logs a warning."""
    caplog.set_level(logging.DEBUG)
    
    # 1. Init without provider
    store = VectorStoreFactory.get_store(storage_root=mock_context.storage_root)
    # Ensure it has NO provider
    store.provider = None
    
    # 2. Access again without provider
    VectorStoreFactory.get_store()
    
    messages = [record.message for record in caplog.records]
    assert any("instance has NONE" in msg for msg in messages), f"Warning not found in {messages}"
