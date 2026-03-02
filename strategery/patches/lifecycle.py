import asyncio
import sys
import signal
import weakref
from typing import List, Callable, Coroutine
from strategery.strategic_logger import strategic_logger

class LifecycleManager:
    """
    Orchestrates the startup and graceful shutdown of all strategic patches.
    This is a singleton managed via the PatchRegistry.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LifecycleManager, cls).__new__(cls)
            cls._instance._init_state()
        return cls._instance

    def _init_state(self):
        self.shutdown_hooks: List[Callable[[], Coroutine]] = []
        self._is_shutting_down = False
        self._loop = None
        self._loop_lock = asyncio.Lock()

    def register_shutdown_hook(self, hook: Callable[[], Coroutine]):
        """Register an async function to be called during shutdown."""
        self.shutdown_hooks.append(hook)
        strategic_logger.debug(f"Registered shutdown hook: {hook.__name__ if hasattr(hook, '__name__') else 'anonymous'}")

    async def _run_shutdown_hooks(self):
        """Executes all registered shutdown hooks in sequence."""
        if self._is_shutting_down:
            return
        self._is_shutting_down = True
        
        strategic_logger.info(f"Executing {len(self.shutdown_hooks)} strategic shutdown hooks...")
        
        for hook in self.shutdown_hooks:
            try:
                await hook()
            except Exception as e:
                strategic_logger.error(f"Error in shutdown hook {hook}: {e}")

    def setup_signal_handlers(self):
        """Sets up handlers for SIGINT, SIGTERM, and SIGBREAK."""
        # Check if we are already in a running loop
        try:
            loop = asyncio.get_running_loop()
            self._loop = loop
            strategic_logger.debug("LifecycleManager: Attached to running event loop.")
        except RuntimeError:
            # No loop yet, we'll try to find it later or when a signal arrives
            strategic_logger.debug("LifecycleManager: No running loop detected during setup. Will acquire on signal.")
            loop = None

        def _handler(sig, frame=None):
            nonlocal loop
            if loop is None:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    # If there's truly no loop, we just exit
                    strategic_logger.warning(f"No active event loop found for signal {sig}. Exiting.")
                    sys.exit(0)

            strategic_logger.warning(f"Received signal {sig}. Initiating graceful strategic shutdown...")
            
            async def _do_shutdown():
                # 1. Run our custom strategic hooks
                await self._run_shutdown_hooks()
                
                # 2. Cancel all remaining tasks ONLY if we are the ones who started the loop
                # If core started the loop, we should let core handle task cancellation
                # to avoid "Event loop is closed" errors when core tries to clean up.
                strategic_logger.info("Strategic shutdown hooks complete. Passing control back to core.")
                
                # If we are in a 'gateway' or long-running core loop, we might need 
                # to stop the loop ourselves if we want a hard stop.
                # However, usually SIGINT will naturally stop the core loop.
                # loop.stop() 

            if loop.is_running():
                asyncio.run_coroutine_threadsafe(_do_shutdown(), loop)
            else:
                sys.exit(0)

        # Register signals
        signals = [signal.SIGINT]
        if sys.platform == 'win32':
            signals.append(signal.SIGBREAK)
        else:
            signals.append(signal.SIGTERM)

        for sig in signals:
            try:
                signal.signal(sig, _handler)
            except Exception as e:
                strategic_logger.debug(f"Could not register signal {sig}: {e}")

# Global singleton
lifecycle_manager = LifecycleManager()
