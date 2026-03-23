import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from telegram import File
from telegram.ext import ExtBot
from strategery.patches.telegram import (
    strategic_get_media_path,
    strategic_detect_thread_metadata,
    strategic_prepare_telegram_media,
    strategic_telegram_on_message,
    strategic_telegram_send,
    TelegramPatch
)

def test_strategic_get_media_path_redirection():
    """Verify that media paths are correctly redirected to the strategic workspace."""
    base = "C:/Storage/workspace"
    # Use backslashes to match the redirection logic's expectation on Windows
    orig = "C:/Users/User/.nanobot\\media/photo.jpg"
    
    # 1. Matching path should be redirected
    new_path = strategic_get_media_path(base, orig)
    assert "C:\\Storage\\workspace\\media\\photo.jpg" in str(new_path)
    
    # 2. Non-matching path should be returned as-is
    other = "C:/Other/path.jpg"
    assert strategic_get_media_path(base, other) == other

def test_strategic_detect_thread_metadata():
    """Verify that thread metadata is correctly extracted from messages."""
    # 1. Thread message
    msg = MagicMock()
    msg.message_thread_id = 123
    res = strategic_detect_thread_metadata(msg, 456)
    assert res["message_thread_id"] == 123
    assert res["session_key_override"] == "telegram:456:123"
    
    # 2. Regular message
    msg.message_thread_id = None
    assert strategic_detect_thread_metadata(msg, 456) is None

def test_strategic_prepare_telegram_media():
    """Verify that the correct sender and parameter are selected based on media type."""
    bot = MagicMock()
    # Mock TelegramChannel._get_media_type (used by the function)
    with patch("nanobot.channels.telegram.TelegramChannel._get_media_type") as mock_type:
        # Photo
        mock_type.return_value = "photo"
        sender, param, mtype = strategic_prepare_telegram_media("p.jpg", bot)
        assert sender == bot.send_photo
        assert param == "photo"
        
        # Voice
        mock_type.return_value = "voice"
        sender, param, mtype = strategic_prepare_telegram_media("v.ogg", bot)
        assert sender == bot.send_voice
        assert param == "voice"

@pytest.mark.asyncio
async def test_telegram_file_redirection_behavior():
    """Behavioral test: Verify that File.download_to_drive redirection logic works."""
    # We test the redirection function used by the patch directly
    workspace = "D:/Nanobot_Storage/workspace"
    custom_path = "C:/Users/User/.nanobot\\media/test.jpg"
    
    new_path = strategic_get_media_path(workspace, custom_path)
    assert "D:\\Nanobot_Storage\\workspace\\media\\test.jpg" in str(new_path)

@pytest.mark.asyncio
async def test_strategic_telegram_send_thread_aware():
    """Verify that send() passes the message_thread_id to the bot."""
    channel = MagicMock()
    channel._app.bot.send_message = AsyncMock()
    channel.config.reply_to_message = False
    
    msg = MagicMock()
    msg.chat_id = "456"
    msg.content = "Hello"
    msg.media = []
    msg.metadata = {"message_thread_id": 123}
    
    with patch("nanobot.utils.helpers.split_message", return_value=["Hello"]), \
         patch("nanobot.channels.telegram._markdown_to_telegram_html", return_value="Hello"):
        await strategic_telegram_send(channel, msg)
        
        args, kwargs = channel._app.bot.send_message.call_args
        assert kwargs["chat_id"] == 456
        assert kwargs["message_thread_id"] == 123
        assert kwargs["text"] == "Hello"
