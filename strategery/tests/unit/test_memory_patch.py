import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
from strategery.patches.memory import MemoryPatch
from strategery.logic import memory_logic
from strategery.logic.config_logic import validate_strategic_config

@pytest.mark.asyncio
async def test_rag_skips_short_generic():
    """Verify RAG is NOT triggered for short or generic messages."""
    patcher = MemoryPatch()
    
    raw_config = {
        "strategic_edition": {"memory_rag": {"enabled": True}},
        "agents": {"defaults": {"contextPruning": {"enabled": False}, "compaction": {"memoryFlush": {"enabled": False}}}}
    }
    config = validate_strategic_config(raw_config)
    
    # Mock dependencies for AgentLoop
    mock_bus = MagicMock()
    mock_provider = MagicMock()
    # Mock chat to return NO_REPLY
    mock_provider.chat = AsyncMock()
    mock_provider.get_default_model.return_value = "gemini-3-flash-preview"
    
    mock_workspace = Path("/tmp/workspace")
    
    from nanobot.agent.loop import AgentLoop
    from nanobot.bus.events import InboundMessage
    
    # Mocking VectorStoreFactory.get_store
    with patch("strategery.patches.vsa.VectorStoreFactory.get_store") as mock_get_store:
        mock_store = AsyncMock()
        mock_get_store.return_value = mock_store
        
        loop = AgentLoop(bus=mock_bus, provider=mock_provider, workspace=mock_workspace)
        # Mock sessions
        mock_session = MagicMock()
        mock_session.messages = []
        mock_session.last_consolidated = 0
        loop.sessions = MagicMock()
        loop.sessions.get_or_create.return_value = mock_session
        
        # Apply the patch with typed config
        patcher._patch_context_pruning(config)
        
        # IMPORTANT: Mock the ORIGINAL process_message so it doesn't run the real logic
        loop._orig_process_message_strategic = AsyncMock()
        
        # 1. Test short message
        msg_short = InboundMessage(content="hi", sender_id="user", channel="test", chat_id="123")
        await loop._process_message(msg_short)
        mock_store.query.assert_not_called()
        
        # 2. Test generic message
        msg_generic = InboundMessage(content="yes", sender_id="user", channel="test", chat_id="123")
        await loop._process_message(msg_generic)
        mock_store.query.assert_not_called()
        
        # 3. Test long descriptive message (should trigger RAG)
        msg_long = InboundMessage(content="Tell me about the real estate market in Colorado Springs.", sender_id="user", channel="test", chat_id="123")
        await loop._process_message(msg_long)
        mock_store.query.assert_called_once()

@pytest.mark.asyncio
async def test_rag_filters_junk_summaries():
    """Verify 'No summary available' is filtered out of RAG results."""
    patcher = MemoryPatch()
    raw_config = {
        "strategic_edition": {"memory_rag": {"enabled": True}},
        "agents": {"defaults": {"contextPruning": {"enabled": False}, "compaction": {"memoryFlush": {"enabled": False}}}}
    }
    config = validate_strategic_config(raw_config)
    
    mock_bus = MagicMock()
    mock_provider = MagicMock()
    mock_provider.chat = AsyncMock()
    mock_provider.get_default_model.return_value = "gemini-3-flash-preview"
    
    mock_workspace = Path("/tmp/workspace")
    
    from nanobot.agent.loop import AgentLoop
    from nanobot.bus.events import InboundMessage
    
    loop = AgentLoop(bus=mock_bus, provider=mock_provider, workspace=mock_workspace)
    # Mock sessions
    mock_session = MagicMock()
    mock_session.messages = []
    mock_session.last_consolidated = 0
    loop.sessions = MagicMock()
    loop.sessions.get_or_create.return_value = mock_session
    
    # Apply with typed config
    patcher._patch_context_pruning(config)
    
    # Mock the ORIGINAL process_message
    loop._orig_process_message_strategic = AsyncMock()
    
    # Mock Vector Store to return junk
    with patch("strategery.patches.vsa.VectorStoreFactory.get_store") as mock_get_store:
        mock_store = AsyncMock()
        mock_store.query.return_value = [
            {"content": "No summary available.", "metadata": {}},
            {"content": "Actual useful fact about Colorado.", "metadata": {}}
        ]
        mock_get_store.return_value = mock_store
        
        msg = InboundMessage(content="Tell me more about Colorado status.", sender_id="user", channel="test", chat_id="123")
        await loop._process_message(msg)
        
        # Verify only the valid fact was injected
        assert "Actual useful fact" in msg.content
        assert "No summary available" not in msg.content
        assert "### RETRIEVED HISTORICAL CONTEXT:" in msg.content
        assert "MAY BE STALE" in msg.content

def test_strategic_get_rolling_journal(tmp_path):
    """Verify that the rolling journal correctly reads the last part of a file."""
    # Setup mock journal directory
    journal_dir = tmp_path / "workspace" / "journal"
    journal_dir.mkdir(parents=True)
    
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    journal_file = journal_dir / f"{today}.md"
    
    # 1. Test non-existent file
    assert memory_logic.get_journal_continuity(tmp_path) == ""
    
    # 2. Test small file
    content = "Entry 1: Started the project.\nEntry 2: Added some patches."
    journal_file.write_text(content, encoding="utf-8-sig")
    result = memory_logic.get_journal_continuity(tmp_path)
    assert "RECENT CONTINUITY" in result
    assert "Entry 1" in result
    assert "Entry 2" in result
    
    # 3. Test large file (truncation)
    long_content = "Header\n" + ("A" * 500) + "\nSplit Point\n" + ("B" * 600)
    journal_file.write_text(long_content, encoding="utf-8-sig")
    # Should get last 1000 chars, then split at first newline
    result = memory_logic.get_journal_continuity(tmp_path, max_chars=1000)
    assert "RECENT CONTINUITY" in result
    assert "Header" not in result
    assert "Split Point" in result
    assert "B" * 600 in result
    assert result.startswith("\n### RECENT CONTINUITY (FROM DAILY JOURNAL):\n...")
