import pytest
from unittest.mock import patch, MagicMock, AsyncMock, mock_open
import json
import os
import sys
import asyncio
from pathlib import Path

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import strategic context
from strategery.patches import STORAGE_ROOT

# Import the standalone logic functions
from strategery.patches.config import strategic_migrate_config
from strategery.patches.provider import strategic_log_provider_request
from strategery.patches.telegram import strategic_get_media_path, strategic_detect_thread_metadata, strategic_prepare_telegram_media
from strategery.patches.subagent import strategic_select_specialist_model
from strategery.patches.memory import strategic_prune_context, strategic_format_consolidation_messages, strategic_parse_consolidation_response

@pytest.fixture
def mock_config_data():
    # Derive a test storage root from the actual configuration or use a generic fallback
    test_storage = (STORAGE_ROOT.parent / "Test_Storage") if STORAGE_ROOT else Path("tmp_storage")
    return {
        "strategic_edition": {
            "user_email": "test@example.com",
            "storage_root": str(test_storage)
        },
        "agents": {
            "defaults": {
                "compaction": {"enabled": True},
                "contextPruning": {"enabled": True},
                "memorySearch": {"enabled": True}
            },
            "consolidator": {"model": "gemini-1.5-pro-test"},
            "specialists": {
                "researcher": {"model": "gemini-1.5-pro", "keywords": ["research"]},
                "architect": {"model": "architect-model", "keywords": ["design"]}
            }
        },
        "memory": {"some": "data"}
    }

def test_strategic_format_consolidation_messages():
    """Verify formatting of messages for consolidation prompt."""
    msgs = [
        {"role": "user", "content": "hello", "timestamp": "2026-03-01T12:00:00"},
        {"role": "assistant", "content": "hi", "timestamp": "2026-03-01T12:01:00"}
    ]
    res = strategic_format_consolidation_messages(msgs)
    assert "[2026-03-01T12:00] USER: hello" in res
    assert "[2026-03-01T12:01] ASSISTANT: hi" in res

def test_strategic_parse_consolidation_response():
    """Verify robust parsing and regex recovery for consolidation responses."""
    current = "Existing facts."
    
    # 1. Clean Tool Call
    args = {"history_entry": "He said hi.", "memory_update": "Facts: hi."}
    res = strategic_parse_consolidation_response(None, True, args, current)
    assert res["history_entry"] == "He said hi."
    
    # 2. Regex Recovery from raw text
    raw_text = 'Here is the JSON: {"history_entry": "Regex success!", "memory_update": "Updated facts."} End.'
    res = strategic_parse_consolidation_response(raw_text, False, None, current)
    assert res["history_entry"] == "Regex success!"
    assert res["memory_update"] == "Updated facts."
    
    # 3. Invalid content
    assert strategic_parse_consolidation_response("No JSON here.", False, None, current) is None

def test_strategic_prepare_telegram_media():
    """Verify selection of correct Telegram sender and param name."""
    mock_bot = MagicMock()
    
    with patch("nanobot.channels.telegram.TelegramChannel._get_media_type") as mock_type:
        # Photo
        mock_type.return_value = "photo"
        sender, param, mtype = strategic_prepare_telegram_media("p.jpg", mock_bot)
        assert sender == mock_bot.send_photo
        assert param == "photo"
        
        # Voice
        mock_type.return_value = "voice"
        sender, param, mtype = strategic_prepare_telegram_media("v.ogg", mock_bot)
        assert sender == mock_bot.send_voice
        assert param == "voice"
        
        # Document (fallback)
        mock_type.return_value = "file"
        sender, param, mtype = strategic_prepare_telegram_media("f.txt", mock_bot)
        assert sender == mock_bot.send_document
        assert param == "document"

def test_strategic_detect_thread_metadata():
    """Verify detection of Telegram message_thread_id and session override."""
    mock_msg = MagicMock()
    mock_msg.message_thread_id = 12345
    
    # Valid thread
    res = strategic_detect_thread_metadata(mock_msg, "678")
    assert res["message_thread_id"] == 12345
    assert res["session_key_override"] == "telegram:678:12345"
    
    # No thread
    mock_msg.message_thread_id = None
    assert strategic_detect_thread_metadata(mock_msg, "678") is None

def test_strategic_select_specialist_model():
    """Verify specialist routing logic based on keywords and broader intent."""
    specs = {
        "researcher": {"model": "r-model", "keywords": ["search"]},
        "architect": {"model": "a-model", "keywords": ["design"]}
    }
    
    # Keyword match
    assert strategic_select_specialist_model("search for files", "Task", specs) == "r-model"
    # Broader intent match
    assert strategic_select_specialist_model("analyze this data", None, specs) == "r-model"
    # Architect intent
    assert strategic_select_specialist_model("refactor the code", "Plan", specs) == "a-model"
    # No match
    assert strategic_select_specialist_model("hello", None, specs) is None

def test_strategic_prune_context():
    """Verify TTL-based pruning and mandatory assistant retention."""
    from datetime import datetime, timedelta
    
    now = datetime.now()
    old = (now - timedelta(hours=10)).isoformat()
    recent = (now - timedelta(minutes=10)).isoformat()
    
    messages = [
        {"role": "assistant", "content": "old 1", "timestamp": old},
        {"role": "assistant", "content": "old 2", "timestamp": old},
        {"role": "assistant", "content": "old 3", "timestamp": old},
        {"role": "user", "content": "recent", "timestamp": recent}
    ]
    
    # Prune with TTL=1h, keep last 2 assistants
    pruned = strategic_prune_context(messages, 1, 2)
    
    contents = [m["content"] for m in pruned]
    assert "old 1" not in contents # Pruned (outside TTL and not in last 2)
    assert "old 2" in contents    # Kept (one of last 2 assistants)
    assert "old 3" in contents    # Kept (one of last 2 assistants)
    assert "recent" in contents   # Kept (User message)

def test_strategic_migrate_config(mock_config_data):
    """Verify that strategic_migrate_config correctly strips custom keys and captures raw config."""
    raw_capture = {}
    data_to_migrate = mock_config_data.copy()
    
    result = strategic_migrate_config(data_to_migrate, raw_capture)
    
    assert "strategic_edition" not in result
    assert "memory" not in result
    assert "compaction" not in result["agents"]["defaults"]
    assert "contextPruning" not in result["agents"]["defaults"]
    assert raw_capture["strategic_edition"]["user_email"] == "test@example.com"

def test_strategic_log_provider_request():
    """Verify that strategic_log_provider_request logs in the expected format."""
    from strategery.strategic_logger import strategic_logger
    with patch.object(strategic_logger, "info") as mock_logger:
        from strategery.patches.provider import strategic_log_provider_request
        strategic_log_provider_request("LiteLLM", "test-model")
        mock_logger.assert_called_with("LiteLLM request: model=test-model")

def test_strategic_get_media_path():
    """Verify that strategic_get_media_path correctly redirects Telegram media."""
    # Pull workspace from config if available, otherwise use a generic name
    workspace = (STORAGE_ROOT / "test_workspace") if STORAGE_ROOT else Path("tmp_workspace")
    # Derive a realistic original path from the user's home directory
    orig_path = Path.home() / ".nanobot" / "media" / "test.jpg"
    
    # It should redirect if it matches the expected .nanobot\media pattern
    new_path = strategic_get_media_path(workspace, orig_path)
    
    # Verify the logic: is the path now anchored in our workspace?
    assert str(workspace) in str(new_path)
    assert "media" in str(new_path)
    assert "test.jpg" in str(new_path)
    
    # It should NOT redirect if it doesn't match
    other_path = Path("/tmp/photo.png")
    assert strategic_get_media_path(workspace, other_path) == other_path

@pytest.mark.asyncio
async def test_strategic_consolidation_flow(tmp_path):
    """Verify the 'Clean History' consolidation flow (Vector Store + Journal)."""
    from strategery.patches.memory import MemoryPatch
    from nanobot.agent.memory import MemoryStore
    
    mock_session = MagicMock()
    mock_session.messages = [{"role": "user", "content": "test", "timestamp": "2026-03-01T12:00:00"}]
    mock_session.last_consolidated = 0
    
    mock_provider = AsyncMock()
    mock_response = MagicMock()
    mock_response.has_tool_calls = False
    mock_response.content = '{"history_entry": "Test summary", "memory_update": "Test facts"}'
    mock_provider.chat.return_value = mock_response
    
    # Use real temp path provided by pytest to allow physical directory creation
    store = MemoryStore(workspace=tmp_path)
    store.read_long_term = MagicMock(return_value="Existing facts")
    store.write_long_term = MagicMock()
    store.append_history = MagicMock() # Should NOT be called in strategic edition
    
    patch_inst = MemoryPatch()
    
    # We patch STORAGE_ROOT in the patches package so the logic uses our tmp_path
    with patch("strategery.patches.vector_store.StrategicVectorStore") as mock_vec_cls, \
         patch("builtins.open", mock_open()) as mock_file, \
         patch("strategery.patches.STORAGE_ROOT", tmp_path):
        
        mock_vec = mock_vec_cls.return_value
        mock_vec.add_entry = AsyncMock(return_value=True)
        
        # Apply patch and run consolidation
        patch_inst.apply({"agents": {"consolidator": {"model": "test-model"}}})
        await store.consolidate(mock_session, mock_provider, "test-model", archive_all=True)
        
        # VERIFY:
        # 1. append_history was NOT called (no bloat)
        store.append_history.assert_not_called()
        # 2. Vector Store WAS called for the entry
        mock_vec.add_entry.assert_any_call("Test summary", {"type": "history_summary", "source": "consolidation"})
        # 3. Daily Journal WAS written (mock_file)
        mock_file.assert_called()
        # 4. Long-term memory was updated
        store.write_long_term.assert_called_with("Test facts")

@pytest.mark.asyncio
async def test_telegram_on_message_no_duplicates():
    """Verify that _on_message only calls the original handler once."""
    from nanobot.channels.telegram import TelegramChannel
    from strategery.patches.telegram import TelegramPatch
    
    patch_inst = TelegramPatch()
    patch_inst.apply({})
    
    mock_channel = MagicMock(spec=TelegramChannel)
    mock_channel._orig_on_message_strategic = AsyncMock()
    
    mock_update = MagicMock()
    mock_update.message.chat_id = 123
    mock_update.message.message_thread_id = 456
    mock_update.message.text = "Hello"
    mock_update.message.photo = None
    mock_update.message.voice = None
    mock_update.message.audio = None
    mock_update.message.document = None
    
    # Run the patched handler
    await TelegramChannel._on_message(mock_channel, mock_update, MagicMock())
    
    # VERIFY: Original handler called exactly ONCE
    assert mock_channel._orig_on_message_strategic.call_count == 1
