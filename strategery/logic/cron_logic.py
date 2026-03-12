from typing import Any, List, Dict, Optional, Tuple
from strategery.strategic_logger import strategic_logger

def should_reload_jobs(current_mtime: float, last_mtime: float, current_size: int, last_size: int) -> bool:
    """Determines if jobs.json needs to be reloaded based on mtime or size change."""
    if current_mtime != last_mtime or current_size != last_size:
        if current_mtime == last_mtime:
            strategic_logger.debug(f"Cron: jobs.json size changed ({current_size}) while mtime remained identical. Reloading.")
        else:
            strategic_logger.info("Cron: jobs.json modified externally, reloading.")
        return True
    return False

def detect_modular_change(items_dir: Any, last_items_mtime: float) -> Tuple[bool, float]:
    """Detects if any modular .md job files have changed in the items directory."""
    if not items_dir.exists():
        return False, 0.0
    
    try:
        current_items_state = sum(f.stat().st_mtime for f in items_dir.glob("*.md"))
        if current_items_state != last_items_mtime:
            return True, current_items_state
    except Exception as ce:
        strategic_logger.debug(f"Cron: Change detection failed: {ce}")
    
    return False, last_items_mtime

def merge_modular_jobs(store_jobs: List[Any], modular_jobs: List[Any], state_cache: Dict[str, Any]) -> List[Any]:
    """Merges modular job definitions into the existing store, preserving state."""
    for mj in modular_jobs:
        # Restore state from cache if available
        if mj.id in state_cache:
            mj.state = state_cache[mj.id]
        
        found = False
        for i, existing in enumerate(store_jobs):
            if existing.id == mj.id:
                # Update existing job definition (Schedule, Payload, Name)
                store_jobs[i].schedule = mj.schedule
                store_jobs[i].payload = mj.payload
                store_jobs[i].name = mj.name
                found = True
                break
        
        if not found:
            store_jobs.append(mj)
            
    return store_jobs

def cache_modular_state(store_jobs: List[Any]) -> Dict[str, Any]:
    """Captures the runtime state of modular jobs for the persistence cache."""
    state_cache = {}
    for job in store_jobs:
        if job.id.startswith("batch_"):
            state_cache[job.id] = job.state
    return state_cache

def resolve_routable_channel(payload: Any, storage_root: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolves a routable channel if the current one is missing or 'cli'.
    Supports [SILENT] prefix in message to force-suppress output delivery.
    """
    current_channel = payload.channel
    message = payload.message or ""

    # MANDATE: If message is marked [SILENT], we explicitly return None to suppress delivery
    if "[SILENT]" in message:
        return None, None

    if not current_channel or current_channel == "cli":
        from strategery.patches.batch import strategic_resolve_job_channel
        try:
            new_channel, new_to = strategic_resolve_job_channel(storage_root)
            if new_channel != "cli":
                return new_channel, new_to
        except Exception as re:
            strategic_logger.error(f"Cron: Channel resolution failed: {re}")

    return current_channel, None

