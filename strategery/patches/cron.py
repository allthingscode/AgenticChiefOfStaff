"""Strategic Patch for CronService: Enhanced Change Detection.
Ensures that CronService correctly reloads jobs.json even when mtime resolution is low (e.g., on Windows).
"""

from loguru import logger
from nanobot.cron.service import CronService
from .base import BasePatch

class CronPatch(BasePatch):
    """Patch for CronService to improve jobs.json reload detection."""

    # Static cache to preserve state of modular jobs across reloads (BUG-069)
    _MODULAR_STATE_CACHE = {}

    @property
    def name(self) -> str:
        return "Cron Service Reliability"

    def apply(self, config: dict) -> bool:
        """Apply the patch to CronService."""
        from .batch import strategic_load_modular_jobs
        from .config import load_strategic_context
        
        orig_load_store = CronService._load_store
        patch_cls = self.__class__

        # We inject a last_size attribute to track file size changes
        def _patched_load_store(self):
            if not hasattr(self, "_last_size"):
                self._last_size = 0
            if not hasattr(self, "_last_items_mtime"):
                self._last_items_mtime = 0

            # Determine if we need to perform the strategic injection
            # (Always on initial load, or if either store file or modular items changed)
            needs_injection = (self._store is None)

            if self._store and self.store_path.exists():
                stat = self.store_path.stat()
                mtime = stat.st_mtime
                size = stat.st_size
                
                # RELOAD IF jobs.json changed
                if mtime != self._last_mtime or size != self._last_size:
                    if mtime == self._last_mtime:
                        logger.debug("Cron: jobs.json size changed while mtime remained identical ({}), reloading", size)
                    else:
                        logger.info("Cron: jobs.json modified externally, reloading")
                    
                    self._store = None
                    self._last_mtime = mtime
                    self._last_size = size
                    needs_injection = True
            
            # Check modular items directory for changes (Hot Reload)
            try:
                from .config import load_strategic_context
                _, _, storage_root = load_strategic_context()
                items_dir = storage_root / "workspace" / "cron" / "items"
                if items_dir.exists():
                    # Simple change detection: sum of mtimes of all .md files
                    current_items_state = sum(f.stat().st_mtime for f in items_dir.glob("*.md"))
                    if current_items_state != self._last_items_mtime:
                        # If modular jobs changed, we force injection even if jobs.json is same
                        needs_injection = True
                        self._last_items_mtime = current_items_state
            except Exception as ce:
                logger.debug(f"Batch: Change detection failed: {ce}")
            
            store = orig_load_store(self)
            
            # STRATEGIC INJECTION: Only perform if necessary (BUG-114 fix)
            if needs_injection:
                try:
                    _, _, storage_root = load_strategic_context()
                    modular_jobs = strategic_load_modular_jobs(storage_root)
                    
                    # Merge modular jobs into the store
                    # We update existing jobs if found, otherwise append
                    for mj in modular_jobs:
                        # RESTORE STATE FROM CACHE (BUG-069)
                        if mj.id in patch_cls._MODULAR_STATE_CACHE:
                            mj.state = patch_cls._MODULAR_STATE_CACHE[mj.id]
                        
                        # Find and update existing job, or append new one
                        found = False
                        for i, existing in enumerate(store.jobs):
                            if existing.id == mj.id:
                                # Update schedule and payload from modular definition (BUG-074)
                                store.jobs[i].schedule = mj.schedule
                                store.jobs[i].payload = mj.payload
                                store.jobs[i].name = mj.name
                                found = True
                                break
                        
                        if not found:
                            store.jobs.append(mj)
                except Exception as be:
                    logger.error(f"Batch: Strategic modular job injection failed: {be}")
            
            # Ensure mtime and size are synced after initial load or manual save
            if self.store_path.exists():
                stat = self.store_path.stat()
                self._last_mtime = stat.st_mtime
                self._last_size = stat.st_size
                
            return store

        # Patch the method
        CronService._load_store = _patched_load_store
        
        # Also patch _save_store to update _last_size AND cache modular state
        orig_save_store = CronService._save_store
        def _patched_save_store(self):
            # Capture state of modular jobs before core wipes them during save
            if self._store:
                for job in self._store.jobs:
                    if job.id.startswith("batch_"):
                        patch_cls._MODULAR_STATE_CACHE[job.id] = job.state

            orig_save_store(self)
            
            if self.store_path.exists():
                self._last_size = self.store_path.stat().st_size
                self._last_mtime = self.store_path.stat().st_mtime

        CronService._save_store = _patched_save_store

        # STRATEGIC FIX (BUG-066): Patch _execute_job to resolve unroutable channels
        if not hasattr(CronService, "_orig_execute_job_strategic"):
            CronService._orig_execute_job_strategic = CronService._execute_job
            
            async def _patched_execute_job(self, job):
                # If channel is missing or 'cli', attempt to find a better one
                if not job.payload.channel or job.payload.channel == "cli":
                    from .batch import strategic_resolve_job_channel
                    from .config import load_strategic_context
                    try:
                        _, _, storage_root = load_strategic_context()
                        new_channel, new_to = strategic_resolve_job_channel(storage_root)
                        
                        if new_channel != "cli":
                            job.payload.channel = new_channel
                            job.payload.to = new_to
                            logger.info("Cron: Redirected job '{}' to routable channel {}:{}", job.name, new_channel, new_to)
                    except Exception as re:
                        logger.error(f"Batch: Channel resolution failed for job {job.id}: {re}")
                
                return await self._orig_execute_job_strategic(job)

            CronService._execute_job = _patched_execute_job
        
        logger.info("Applied Cron Service Reliability patch (Enhanced Reload Detection)")
        return True
