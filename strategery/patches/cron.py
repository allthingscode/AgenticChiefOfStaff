from nanobot.cron.service import CronService
from .base import BasePatch, PatchResult, PatchContext
from strategery.strategic_logger import strategic_logger
from strategery.logic import cron_logic

class CronPatch(BasePatch):
    """Thin Bridge for CronService reload detection and modular job injection."""

    # Static cache to preserve state of modular jobs across reloads (BUG-069)
    _MODULAR_STATE_CACHE = {}

    @property
    def name(self) -> str:
        return "Cron Service Reliability"

    def apply(self, context: PatchContext) -> PatchResult:
        result = PatchResult(patch_name=self.name, success=True)
        try:
            from .batch import strategic_load_modular_jobs
            
            orig_load_store = CronService._load_store
            patch_cls = self.__class__

            def _patched_load_store(self):
                # 1. Initialization
                if not hasattr(self, "_last_size"): self._last_size = 0
                if not hasattr(self, "_last_mtime"): self._last_mtime = 0
                if not hasattr(self, "_last_items_mtime"): self._last_items_mtime = 0.0

                # 2. Change Detection
                needs_injection = (self._store is None)
                
                # jobs.json reload check
                if self._store and self.store_path.exists():
                    stat = self.store_path.stat()
                    if cron_logic.should_reload_jobs(stat.st_mtime, self._last_mtime, stat.st_size, self._last_size):
                        self._store = None
                        needs_injection = True
                
                # modular items reload check
                try:
                    items_dir = context.workspace_root / "cron" / "items"
                    changed, new_mtime = cron_logic.detect_modular_change(items_dir, self._last_items_mtime)
                    if changed:
                        needs_injection = True
                        self._last_items_mtime = new_mtime
                except: pass
                
                # 3. Execution
                store = orig_load_store(self)
                
                if needs_injection:
                    try:
                        modular_jobs = strategic_load_modular_jobs(context.storage_root)
                        store.jobs = cron_logic.merge_modular_jobs(store.jobs, modular_jobs, patch_cls._MODULAR_STATE_CACHE)
                    except Exception as be:
                        strategic_logger.error(f"Batch: Modular injection failed: {be}")
                
                # 4. Final state capture
                if self.store_path.exists():
                    stat = self.store_path.stat()
                    self._last_mtime, self._last_size = stat.st_mtime, stat.st_size
                
                # First-load edge case: if we just injected, ensure items_mtime is up to date
                try:
                    items_dir = context.workspace_root / "cron" / "items"
                    _, self._last_items_mtime = cron_logic.detect_modular_change(items_dir, 0)
                except: pass
                    
                return store

            CronService._load_store = _patched_load_store
            result.affected_symbols.append("CronService._load_store")
            
            orig_save_store = CronService._save_store
            def _patched_save_store(self):
                if self._store:
                    patch_cls._MODULAR_STATE_CACHE.update(cron_logic.cache_modular_state(self._store.jobs))
                orig_save_store(self)
                if self.store_path.exists():
                    stat = self.store_path.stat()
                    self._last_mtime, self._last_size = stat.st_mtime, stat.st_size
            CronService._save_store = _patched_save_store
            result.affected_symbols.append("CronService._save_store")

            if not hasattr(CronService, "_orig_execute_job_strategic"):
                CronService._orig_execute_job_strategic = CronService._execute_job
                async def _patched_execute_job(self, job):
                    new_chan, new_to = cron_logic.resolve_routable_channel(job.payload.channel, context.storage_root)
                    if new_chan and new_chan != job.payload.channel:
                        job.payload.channel = new_chan
                        if new_to: job.payload.to = new_to
                    return await self._orig_execute_job_strategic(job)
                CronService._execute_job = _patched_execute_job
                result.affected_symbols.append("CronService._execute_job")
            
            return result
        except Exception as e:
            import traceback
            result.success = False
            result.error_msg = str(e)
            result.traceback = traceback.format_exc()
            strategic_logger.error(f"Cron patch error: {e}")
            return result
