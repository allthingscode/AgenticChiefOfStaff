import asyncio
from unittest.mock import MagicMock, patch

import pytest

from strategery.patches.lifecycle import LifecycleManager


@pytest.fixture
def manager():
    """Create a fresh lifecycle manager for each test."""
    # Reset singleton
    LifecycleManager._instance = None
    m = LifecycleManager()
    return m

def test_hook_registration(manager):
    """Verify that hooks are correctly registered."""
    def mock_hook():
        pass

    manager.register_shutdown_hook(mock_hook)
    assert mock_hook in manager.shutdown_hooks

@pytest.mark.asyncio
async def test_run_shutdown_hooks_execution(manager):
    """Verify that all registered hooks are executed."""
    hook1 = MagicMock()
    hook2 = MagicMock()

    async def async_hook1():
        hook1()

    async def async_hook2():
        hook2()

    manager.register_shutdown_hook(async_hook1)
    manager.register_shutdown_hook(async_hook2)

    await manager._run_shutdown_hooks()

    hook1.assert_called_once()
    hook2.assert_called_once()
    assert manager._is_shutting_down is True

@pytest.mark.asyncio
async def test_run_shutdown_hooks_error_resilience(manager):
    """Verify that one hook failing doesn't stop others from running."""
    async def failing_hook():
        raise Exception("Hook Failed")

    hook2 = MagicMock()
    async def async_hook2():
        hook2()

    manager.register_shutdown_hook(failing_hook)
    manager.register_shutdown_hook(async_hook2)

    # This should not raise
    await manager._run_shutdown_hooks()

    hook2.assert_called_once()

def test_setup_signal_handlers_no_loop(manager):
    """Verify signal handlers setup doesn't crash without a loop."""
    with patch("asyncio.get_running_loop", side_effect=RuntimeError("no running loop")):
        manager.setup_signal_handlers()
        # Should just return gracefully
        assert True

@pytest.mark.asyncio
async def test_periodic_handler_refresh_loop(manager):
    """Verify periodic refresh task starts and can be cancelled."""
    with patch("asyncio.get_running_loop") as mock_loop:
        mock_loop.return_value = asyncio.get_running_loop()
        manager.setup_signal_handlers()

        assert manager._refresh_task is not None
        # We don't want it running forever in tests
        manager._is_shutting_down = True
        await asyncio.sleep(0.1)
        if manager._refresh_task:
            manager._refresh_task.cancel()
