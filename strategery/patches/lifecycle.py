import asyncio
import sys
import os
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
        self._orig_handlers = {}

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
        """Sets up handlers for SIGINT, SIGTERM, and SIGBREAK with core handoff."""
        # Check if we are already in a running loop
        try:
            loop = asyncio.get_running_loop()
            self._loop = loop
            strategic_logger.debug("LifecycleManager: Attached to running event loop.")
        except RuntimeError:
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
                # 1. Run our custom strategic hooks (e.g. close Vector Store)
                await self._run_shutdown_hooks()
                
                # 2. Strategic Handoff: Restore original handlers and re-send signal
                # This allows the core Nanobot to receive the signal and shut itself down.
                strategic_logger.info("Strategic shutdown hooks complete. Passing control back to core.")
                
                orig = self._orig_handlers.get(sig)
                if orig and callable(orig):
                    # Restore and invoke the original core handler
                    signal.signal(sig, orig)
                    if sig == signal.SIGINT:
                        # Special handling for SIGINT to ensure it propagates correctly
                        # Most Python apps expect KeyboardInterrupt to be raised or the handler to run
                        os.kill(os.getpid(), sig)
                    else:
                        # For other signals, we just call the handler directly if possible
                        try: orig(sig, frame)
                        except: pass
                
                # 3. SAFETY: If core still hangs for more than 5 seconds, force exit
                await asyncio.sleep(5)
                strategic_logger.warning("Core shutdown timed out. Forcing process exit.")
                os._exit(0)

            if loop.is_running():
                asyncio.run_coroutine_threadsafe(_do_shutdown(), loop)
            else:
                sys.exit(0)

        # Register signals and capture originals
        signals = [signal.SIGINT]
        if sys.platform == 'win32':
            signals.append(signal.SIGBREAK)
        else:
            signals.append(signal.SIGTERM)

        for sig in signals:
            try:
                # Capture original handler if not already ours
                current = signal.getsignal(sig)
                if current != _handler:
                    self._orig_handlers[sig] = current
                
                signal.signal(sig, _handler)
            except Exception as e:
                strategic_logger.debug(f"Could not register signal {sig}: {e}")

# Global singleton
lifecycle_manager = LifecycleManager()
