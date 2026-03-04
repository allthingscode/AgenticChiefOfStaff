"""Strategic Patch for CronService: Enhanced Change Detection.
Ensures that CronService correctly reloads jobs.json even when mtime resolution is low (e.g., on Windows).
"""

from loguru import logger
from nanobot.cron.service import CronService
from .base import BasePatch

class CronPatch(BasePatch):
    """Patch for CronService to improve jobs.json reload detection."""

    @property
    def name(self) -> str:
        return "Cron Service Reliability"

    def apply(self, config: dict) -> bool:
        """Apply the patch to CronService."""
        orig_load_store = CronService._load_store

        # We inject a last_size attribute to track file size changes
        def _patched_load_store(self):
            if not hasattr(self, "_last_size"):
                self._last_size = 0

            if self._store and self.store_path.exists():
                stat = self.store_path.stat()
                mtime = stat.st_mtime
                size = stat.st_size
                
                # RELOAD IF:
                # 1. mtime changed
                # 2. size changed (mtime might be the same on high-speed writes)
                if mtime != self._last_mtime or size != self._last_size:
                    if mtime == self._last_mtime:
                        logger.debug("Cron: jobs.json size changed while mtime remained identical ({}), reloading", size)
                    else:
                        logger.info("Cron: jobs.json modified externally, reloading")
                    
                    self._store = None
                    self._last_mtime = mtime
                    self._last_size = size
            
            store = orig_load_store(self)
            
            # Ensure _last_size is synced after initial load or manual save
            if self.store_path.exists():
                self._last_size = self.store_path.stat().st_size
                
            return store

        # Patch the method
        CronService._load_store = _patched_load_store
        
        # Also patch _save_store to update _last_size
        orig_save_store = CronService._save_store
        def _patched_save_store(self):
            orig_save_store(self)
            if self.store_path.exists():
                self._last_size = self.store_path.stat().st_size
                self._last_mtime = self.store_path.stat().st_mtime

        CronService._save_store = _patched_save_store
        
        logger.info("Applied Cron Service Reliability patch (Enhanced Reload Detection)")
        return True
