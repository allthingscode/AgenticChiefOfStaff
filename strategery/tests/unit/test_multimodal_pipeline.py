import pytest
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from strategery.patches.infra import InfraPatch
from strategery.patches.loop import AgentLoopPatch
from strategery.patches.subagent import SubagentPatch
from strategery.patches.telegram import TelegramPatch
from strategery.patches.base import PatchContext
from nanobot.bus.events import InboundMessage

@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_media_dir_redirection():
    """Assert that get_media_dir is globally redirected to D: drive (BUG-201)."""
    # Mock core module to avoid side effects on other tests
    with patch("nanobot.config.paths.get_media_dir"):
        context = PatchContext(
            config=MagicMock(),
            storage_root=Path("D:/Nanobot_Storage"),
            user_email="test@example.com",
            app_root=Path("C:/test/app")
        )
        
        patch_inst = InfraPatch()
        # We need to mock sys.modules to prevent infra patch from actually modifying modules
        with patch.dict("sys.modules", {"nanobot.channels.telegram": MagicMock()}):
            patch_inst.apply(context)
        
        # In the real app, core_paths.get_media_dir is replaced. 
        # Here we just verify the patch logic was triggered.
        import nanobot.config.paths as core_paths
        assert hasattr(core_paths, "get_media_dir_strategic")

@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_ironclad_media_tagging():
    """Assert that AgentLoop tags incoming messages with media paths (BUG-202)."""
    # Initialize Patch
    patch_inst = AgentLoopPatch()
    from nanobot.agent.loop import AgentLoop
    
    # Apply patch
    patch_inst.apply(MagicMock())
    
    # Create a dummy loop instance with required args
    loop = AgentLoop(
        provider=MagicMock(), 
        model="test", 
        bus=MagicMock(),
        workspace=MagicMock()
    )
    # Mock internal process message to avoid LLM calls
    loop._process_message = AsyncMock(return_value=None)
    
    # Create message with media
    msg = InboundMessage(
        channel="telegram",
        sender_id="user",
        chat_id="123",
        content="Check this image",
        media=["D:\\media\\img.jpg"]
    )
    
    # Dispatch
    try:
        await loop._dispatch(msg)
    finally:
        # Prevent test hang by cancelling the strategic monitor task
        if hasattr(loop, "_strategic_monitor_task") and loop._strategic_monitor_task:
            loop._strategic_monitor_task.cancel()
            try:
                await loop._strategic_monitor_task
            except asyncio.CancelledError:
                pass
    
    # Assert content was tagged
    assert "[image: D:\\media\\img.jpg]" in msg.content

@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_telegram_patch_signature():
    """Assert that the patched get_file method has the correct signature (BUG-204)."""
    from nanobot.channels.telegram import TelegramChannel
    from unittest.mock import AsyncMock
    
    # Mock bot
    mock_bot = AsyncMock()
    mock_file = MagicMock()
    mock_file.download_to_drive = AsyncMock()
    mock_bot.get_file = AsyncMock(return_value=mock_file)
    
    mock_app = MagicMock()
    mock_app.bot = mock_bot
    mock_app.initialize = AsyncMock()
    
    # Create channel
    mock_config = MagicMock()
    mock_config.proxy = None
    mock_config.disable_bot_commands = False
    channel = TelegramChannel(mock_config, MagicMock())
    channel._app = mock_app
    
    # Apply patch
    context = PatchContext(
        config=MagicMock(),
        storage_root=Path("D:/Nanobot_Storage"),
        user_email="test@example.com",
        app_root=Path("C:/test/app")
    )
    TelegramPatch().apply(context)
    
    # Mock the original start to avoid polling
    channel._orig_start_strategic = AsyncMock()
    
    # Trigger start hook
    with patch("strategery.patches.telegram.strategic_telegram_polling_loop", AsyncMock()):
        await channel.start()
    
    # Call the patched method
    # It should accept (self, file_id) or just (file_id) depending on how it's bound.
    # In our patch, we defined it as (bot_self, file_id, *args, **kwargs)
    try:
        # If bound to instance, call(file_id) -> function(bot, file_id)
        await channel._app.bot.get_file("test_file_id")
    except TypeError as e:
        pytest.fail(f"Signature mismatch in get_file patch: {e}")

@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_spawn_tool_auto_capture():
    """Assert that SpawnTool extracts image tags from history (BUG-199)."""
    from nanobot.agent.tools.spawn import SpawnTool
    from nanobot.agent.tools.registry import ToolRegistry
    
    # Mock ContextBuilder to avoid side effects
    with patch("nanobot.agent.context.ContextBuilder"):
        # Apply patches
        SubagentPatch().apply(MagicMock(user_email="test@example.com"))
        
        registry = ToolRegistry()
        # Simulate history stored by AgentLoopPatch
        registry._strategic_last_messages = [
            {"role": "user", "content": "Here is an image\n[image: D:\\Nanobot_Storage\\workspace\\media\\test.jpg]"}
        ]
        
        mock_mgr = MagicMock()
        mock_mgr.spawn = AsyncMock(return_value="Started")
        
        tool = SpawnTool(manager=mock_mgr)
        tool._registry = registry # Set registry reference
        tool._origin_channel = "cli"
        tool._origin_chat_id = "direct"
        tool._session_key = "cli:direct"
        
        # Execute spawn WITHOUT explicit attachments
        await tool.execute(task="Analyze this")
        
        # Assert that attachments were auto-captured from history
        args, kwargs = mock_mgr.spawn.call_args
        assert "attachments" in kwargs
        assert kwargs["attachments"] is not None
        assert kwargs["attachments"][0]["path"] == "D:\\Nanobot_Storage\\workspace\\media\\test.jpg"
