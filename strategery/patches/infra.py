import sys
import os
import io
import asyncio
from functools import wraps
from . import BasePatch

class InfraPatch(BasePatch):
    """Handles Windows-specific infrastructure fixes and UTF-8 enforcement."""
    
    @property
    def name(self) -> str:
        return "Infrastructure (Windows/UTF-8)"

    def apply(self, config: dict) -> bool:
        # 1. Force UTF-8 encoding for Windows stdout/stderr
        if sys.platform == 'win32':
            # Only wrap if not already utf-8 to avoid breaking pytest/capture
            if getattr(sys.stdout, 'encoding', '').lower() != 'utf-8':
                try:
                    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
                    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
                except (AttributeError, io.UnsupportedOperation):
                    pass # Already wrapped or doesn't support buffering
            
            os.environ["PYTHONIOENCODING"] = "utf-8"
            os.environ["PYTHONUTF8"] = "1"

        # 2. Fix the Windows 'Event loop is closed' error
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
        
        return True
