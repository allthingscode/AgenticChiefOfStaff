import sys
import os
import io
import asyncio
import signal
from functools import wraps
from . import BasePatch

class InfraPatch(BasePatch):
    """Handles Windows-specific infrastructure fixes, lifecycle management, and UTF-8 enforcement."""

    @property
    def name(self) -> str:
        return "Infrastructure (Windows/UTF-8)"

    def apply(self, config: dict) -> bool:
        # 1. Force UTF-8 encoding for Windows stdout/stderr
        if sys.platform == 'win32':
            if getattr(sys.stdout, 'encoding', '').lower() != 'utf-8':
                try:
                    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
                    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
                except (AttributeError, io.UnsupportedOperation):
                    pass

            os.environ["PYTHONIOENCODING"] = "utf-8"
            os.environ["PYTHONUTF8"] = "1"

        # 2. Strategic Lifecycle & Signal Handling
        def _setup_lifecycle():
            loop = asyncio.get_event_loop()

            def _shutdown_handler(sig, frame=None):
                print(f"\n[Strategic] Received signal {sig}, initiating graceful shutdown...")

                # Create a task to handle the async part of shutdown
                async def _async_shutdown():
                    # 1. Cancel all running tasks
                    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
                    [task.cancel() for task in tasks]

                    if tasks:
                        print(f"[Strategic] Cancelling {len(tasks)} active tasks...")
                        await asyncio.gather(*tasks, return_exceptions=True)

                    # 2. Perform any final strategic flushes (e.g., MemoryStore)
                    try:
                        from nanobot.agent.memory import MemoryStore
                        # If a store instance exists, we might want to flush it
                        # Since this is global, we search for it or use the singleton
                    except ImportError:
                        pass

                    print("[Strategic] Shutdown complete. Goodbye.")
                    loop.stop()

                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(_async_shutdown(), loop)
                else:
                    sys.exit(0)

            # Register signals (Windows supports SIGINT and SIGTERM/SIGBREAK)
            signal.signal(signal.SIGINT, _shutdown_handler)
            if sys.platform != 'win32':
                signal.signal(signal.SIGTERM, _shutdown_handler)
            else:
                signal.signal(signal.SIGBREAK, _shutdown_handler)

        # 3. Fix the Windows 'Event loop is closed' error and set policy
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

            from asyncio.proactor_events import _ProactorBasePipeTransport

            if not hasattr(_ProactorBasePipeTransport, "_orig_del_strategic"):
                _ProactorBasePipeTransport._orig_del_strategic = _ProactorBasePipeTransport.__del__

                @wraps(_ProactorBasePipeTransport._orig_del_strategic)
                def _patched_del(self):
                    try:
                        self._orig_del_strategic()
                    except (RuntimeError, ValueError) as e:
                        _msg = str(e)
                        if 'Event loop is closed' in _msg or 'I/O operation on closed pipe' in _msg:
                            pass
                        else:
                            raise
                _ProactorBasePipeTransport.__del__ = _patched_del

        # Inject lifecycle setup after the loop is likely to be initialized
        try:
            # get_running_loop() is the modern way and does not warn
            loop = asyncio.get_running_loop()
            if loop.is_running():
                _setup_lifecycle()
        except RuntimeError:
            # No loop is running yet, which is expected during some initializations
            pass

        return True

