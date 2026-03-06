import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from strategery.patches.memory import (
    strategic_prune_context,
    strategic_inject_rag_context,
    strategic_write_journal_entry,
    strategic_get_rolling_journal
)

def test_strategic_prune_context():
    """Verify that context pruning respects TTL and mandatory assistant retention."""
    now = datetime.now()
    messages = [
        {"role": "user", "content": "Old user", "timestamp": (now - timedelta(hours=10)).isoformat()},
        {"role": "assistant", "content": "Old assistant 1", "timestamp": (now - timedelta(hours=9)).isoformat()},
        {"role": "assistant", "content": "Old assistant 2", "timestamp": (now - timedelta(hours=8)).isoformat()},
        {"role": "assistant", "content": "Old assistant 3", "timestamp": (now - timedelta(hours=7)).isoformat()},
        {"role": "user", "content": "New user", "timestamp": (now - timedelta(hours=1)).isoformat()},
    ]
    
    # Prune with 6h TTL, keep last 2 assistants
    # Expected: "New user" (new), "Old user" (user always kept), "Old assistant 3" (last 1), "Old assistant 2" (last 2)
    # "Old assistant 1" should be dropped.
    pruned = strategic_prune_context(messages, ttl_hours=6, keep_last_assistants=2)
    
    contents = [m["content"] for m in pruned]
    assert "Old user" in contents
    assert "New user" in contents
    assert "Old assistant 3" in contents
    assert "Old assistant 2" in contents
    assert "Old assistant 1" not in contents

@pytest.mark.asyncio
async def test_strategic_inject_rag_context_success():
    """Verify that RAG injection returns formatted context for valid queries."""
    provider = MagicMock()
    vec_store_factory = MagicMock()
    mock_vec = AsyncMock()
    vec_store_factory.get_store.return_value = mock_vec
    
    mock_vec.query.return_value = [
        {"content": "Fact 1"},
        {"content": "Fact 2"}
    ]
    
    content = "What is the project status?"
    block, count = await strategic_inject_rag_context(content, provider, vec_store_factory)
    
    assert count == 2
    assert "### RETRIEVED HISTORICAL CONTEXT" in block
    assert "Fact 1" in block
    assert "Fact 2" in block

@pytest.mark.asyncio
async def test_strategic_inject_rag_context_generic_filter():
    """Verify that RAG is NOT triggered for generic or short messages."""
    provider = MagicMock()
    
    # 1. Short message
    block, count = await strategic_inject_rag_context("Hi", provider)
    assert block is None
    
    # 2. Generic message
    block, count = await strategic_inject_rag_context("Yes, please.", provider)
    assert block is None

def test_strategic_write_journal_entry(tmp_path):
    """Verify that consolidation entries are written to the daily journal."""
    entry = "Test consolidation summary."
    success = strategic_write_journal_entry(tmp_path, entry)
    
    assert success is True
    today = datetime.now().strftime("%Y-%m-%d")
    journal_path = tmp_path / "workspace" / "memory" / f"{today}.md"
    assert journal_path.exists()
    content = journal_path.read_text(encoding="utf-8-sig")
    assert "### CONSOLIDATION" in content
    assert entry in content

def test_strategic_get_rolling_journal(tmp_path):
    """Verify that recent journal snippets are correctly retrieved."""
    today = datetime.now().strftime("%Y-%m-%d")
    journal_dir = tmp_path / "workspace" / "memory"
    journal_dir.mkdir(parents=True)
    journal_path = journal_dir / f"{today}.md"
    
    text = "Line 1\nLine 2\nLine 3"
    journal_path.write_text(text, encoding="utf-8-sig")
    
    # Requesting a small amount should return the end of the file
    snippet = strategic_get_rolling_journal(tmp_path, max_chars=10)
    assert "Line 3" in snippet
    assert "Line 1" not in snippet
