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

# Import the standalone logic functions
from strategery.patches.config import strategic_migrate_config
from strategery.patches.provider import strategic_log_provider_request
from strategery.patches.telegram import strategic_get_media_path, strategic_detect_thread_metadata, strategic_prepare_telegram_media
from strategery.patches.subagent import strategic_select_specialist_model
from strategery.patches.memory import strategic_prune_context, strategic_format_consolidation_messages, strategic_parse_consolidation_response

@pytest.fixture
def mock_config_data():
    return {
        "strategic_edition": {
            "user_email": "test@example.com",
            "storage_root": "D:/Test_Storage"
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
    from loguru import logger
    with patch.object(logger, "info") as mock_logger:
        strategic_log_provider_request("LiteLLM", "test-model")
        mock_logger.assert_called_with("[Strategic] {} request: model={}", "LiteLLM", "test-model")

def test_strategic_get_media_path():
    """Verify that strategic_get_media_path correctly redirects Telegram media."""
    workspace = "D:/Nanobot_Storage/workspace"
    orig_path = r"C:\Users\Admin\.nanobot\media\test.jpg"
    
    # It should redirect if it matches the expected .nanobot\media pattern
    new_path = strategic_get_media_path(workspace, orig_path)
    assert "D:\\Nanobot_Storage\\workspace\\media\\test.jpg" in str(Path(new_path))
    
    # It should NOT redirect if it doesn't match
    other_path = r"C:\Temp\photo.png"
    assert strategic_get_media_path(workspace, other_path) == other_path

@pytest.mark.asyncio
async def test_telegram_media_redirection_logic():
    """Verify the integration of Telegram media redirection."""
    from nanobot.channels.telegram import TelegramChannel
    from strategery.patches.telegram import TelegramPatch
    
    patch_inst = TelegramPatch()
    patch_inst.apply({})
    
    mock_channel = MagicMock(spec=TelegramChannel)
    mock_channel.config = MagicMock()
    mock_channel.config.workspace_path = "D:/Test_Workspace"
    
    mock_context = MagicMock()
    mock_file = MagicMock()
    
    captured_paths = []
    async def final_download(custom_path=None, *args, **kwargs):
        captured_paths.append(custom_path)
        return True
    
    mock_file.download_to_drive = final_download
    mock_context.bot.get_file = AsyncMock(return_value=mock_file)
    
    # Mock update message structure
    mock_update = MagicMock()
    mock_update.message.photo = [MagicMock()]
    mock_update.message.voice = None
    mock_update.message.audio = None
    mock_update.message.document = None
    mock_update.message.message_thread_id = None

    with patch.object(TelegramChannel, "_orig_on_message_strategic", new_callable=AsyncMock):
        await TelegramChannel._on_message(mock_channel, mock_update, mock_context)
        
        # Trigger the patched get_file
        patched_file = await mock_context.bot.get_file("file_id")
        
        # Trigger the patched download
        await patched_file.download_to_drive(custom_path=r".nanobot\media\photo.jpg")
        
        assert any("Test_Workspace" in str(p) for p in captured_paths)
        assert any("media" in str(p) for p in captured_paths)
        assert any("photo.jpg" in str(p) for p in captured_paths)
