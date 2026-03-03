import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from telegram.error import NetworkError
from strategery.patches.telegram import TelegramPatch
from strategery.strategic_logger import strategic_logger

# Define a real class for the patcher to work on
class MockTelegramChannel:
    async def start(self):
        # We simulate the start_polling call that the real start() would make
        await self._app.updater.start_polling()
        
    async def _on_message(self, update, context):
        pass
    def _stop_typing(self, chat_id):
        pass
    @staticmethod
    def _get_media_type(path):
        return "photo"

@pytest.mark.asyncio
async def test_telegram_polling_resilience():
    """Verify that TelegramChannel retries polling on NetworkError."""
    # Mock TelegramChannel and its dependencies
    mock_app = MagicMock()
    mock_app.updater = MagicMock()
    mock_app.updater.running = False
    
    # Track calls to start_polling
    start_polling_mock = AsyncMock()
    mock_app.updater.start_polling = start_polling_mock
    
    # Instance of our mock class
    channel = MockTelegramChannel()
    channel._app = mock_app
    channel._running = True
    channel.config = MagicMock()
    channel.config.token = "fake_token"
    channel._handle_message = AsyncMock()
    
    # Apply the patch logic
    patcher = TelegramPatch()
    patcher._patch_telegram_channel(MockTelegramChannel, {})
    
    # Setup the failure scenario
    call_count = 0
    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        strategic_logger.info(f"TEST: start_polling call {call_count}")
        
        if call_count == 1:
            mock_app.updater.running = True
            return
            
        if call_count == 2:
            mock_app.updater.running = False
            raise NetworkError("Transient network failure")
            
        mock_app.updater.running = True

    start_polling_mock.side_effect = side_effect

    # We DON'T mock sleep here, we let it run so the loop actually works
    # But we'll use a very small retry_delay in the patch if we could.
    # Since we can't easily change the delay in the patch, we'll just wait.
    
    start_task = asyncio.create_task(channel.start())
    
    # Monitor and force state changes
    try:
        # Wait for first call
        for _ in range(50):
            if start_polling_mock.call_count >= 1: break
            await asyncio.sleep(0.01)
        
        # Trigger second call by flipping running
        mock_app.updater.running = False
        
        # Wait for second call (the one that fails) and third call (the retry)
        for _ in range(200):
            if start_polling_mock.call_count >= 3: break
            # Ensure updater.running stays false to keep triggering restart 
            # until call 3 sets it back to true
            if start_polling_mock.call_count == 2:
                mock_app.updater.running = False
            await asyncio.sleep(0.05)
            
    finally:
        # Stop the channel
        channel._running = False
        try:
            await asyncio.wait_for(start_task, timeout=1.0)
        except:
            pass

    # Should have called at least 3 times
    assert start_polling_mock.call_count >= 3
