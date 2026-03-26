import asyncio
import os
import signal
import sys
from typing import Callable, Coroutine, List

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
        self._orig_handlers = {}
        self._refresh_task = None

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
        # 1. Immediate capture of existing handlers
        self._capture_handlers()

        # 2. Setup periodic refresh to catch core handlers set later
        try:
            loop = asyncio.get_running_loop()
            self._loop = loop
            if not self._refresh_task or self._refresh_task.done():
                self._refresh_task = loop.create_task(self._periodic_handler_refresh())
        except RuntimeError:
            pass

        def _handler(sig, frame=None):
            strategic_logger.warning(f"Received signal {sig}. Initiating graceful strategic shutdown...")

            # Use current loop or find it
            current_loop = self._loop
            if not current_loop:
                try: current_loop = asyncio.get_running_loop()
                except RuntimeError: pass

            async def _do_shutdown():
                # A. Run our custom strategic hooks
                await self._run_shutdown_hooks()

                # B. Strategic Handoff: Restore original handlers and re-trigger
                strategic_logger.info("Strategic shutdown hooks complete. Passing control back to core.")

                orig = self._orig_handlers.get(sig)
                # Restore original
                try: signal.signal(sig, orig or signal.SIG_DFL)
                except: pass

                # Trigger core shutdown
                if sig == signal.SIGINT or (hasattr(signal, 'SIGBREAK') and sig == signal.SIGBREAK):
                    # For terminal-driven apps, re-sending the signal to our own PID
                    # is the most reliable way to trigger KeyboardInterrupt in the main thread.
                    os.kill(os.getpid(), sig)
                elif orig and callable(orig):
                    try: orig(sig, frame)
                    except: pass

                # C. SAFETY: If core still hangs for more than 10 seconds, force exit
                await asyncio.sleep(10)
                strategic_logger.warning("Core shutdown timed out. Forcing process exit.")
                os._exit(0)

            if current_loop and current_loop.is_running():
                asyncio.run_coroutine_threadsafe(_do_shutdown(), current_loop)
            else:
                # If no loop, we can't run async hooks easily, just try to exit
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

    def _capture_handlers(self):
        """Captures handlers that are NOT our own."""
        signals = [signal.SIGINT]
        if sys.platform == 'win32': signals.append(signal.SIGBREAK)
        else: signals.append(signal.SIGTERM)

        for sig in signals:
            try:
                current = signal.getsignal(sig)
                # Only capture if it's not our own wrapper
                if current and "_handler" not in str(current):
                    self._orig_handlers[sig] = current
            except:
                pass

    async def _periodic_handler_refresh(self):
        """Background task to periodically capture handlers set by core later."""
        while not self._is_shutting_down:
            self._capture_handlers()
            await asyncio.sleep(2.0)

# Global singleton
lifecycle_manager = LifecycleManager()
