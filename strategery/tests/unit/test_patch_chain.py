from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.bus.events import InboundMessage
from strategery.patches import registry
from strategery.patches.base import PatchContext


@pytest.mark.asyncio
async def test_process_message_patch_chain():
    """Verify the entire patch chain for _process_message executes without TypeError."""

    # 1. Mock Core dependencies
    mock_provider = MagicMock()
    mock_provider.chat = AsyncMock()

    # Setup context
    context = PatchContext(
        config=MagicMock(),
        storage_root="D:/Nanobot_Storage",
        user_email="test@example.com",
        app_root="C:/test"
    )

    # 2. Apply patches
    registry.apply_all(context)

    # 3. Create AgentLoop instance
    # We need to mock enough of AgentLoop to avoid __init__ failures
    loop_inst = MagicMock(spec=AgentLoop)
    loop_inst.provider = mock_provider
    loop_inst.model = "test-model"
    loop_inst.sessions = MagicMock()
    loop_inst.context = MagicMock()
    loop_inst.tools = MagicMock()
    loop_inst.bus = MagicMock()

    # Set the patched methods back onto the instance if needed,
    # but patches usually target the CLASS.

    msg = InboundMessage(
        channel="telegram",
        sender_id="user123",
        chat_id="chat123",
        content="Hello"
    )

    # We want to call the ACTUAL patched method on the class
    # Since it's an async method, we await it.
    try:
        # Note: _process_message is a class method that's been patched.
        # Calling it via the class requires passing 'self' (loop_inst).
        await AgentLoop._process_message(loop_inst, msg)
    except TypeError as e:
        pytest.fail(f"Patch chain failed with TypeError: {e}")
    except Exception as e:
        # Other exceptions are okay for this test as long as it's not a signature mismatch
        print(f"Caught expected non-TypeError: {e}")
