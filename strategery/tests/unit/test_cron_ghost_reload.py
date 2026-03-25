import pytest
from unittest.mock import patch
from nanobot.cron.service import CronService
from strategery.patches.cron import CronPatch

@pytest.mark.asyncio
async def test_cron_ghost_reload_prevention(mock_context, tmp_path):
    """Verify that multiple calls to _load_store only trigger strategic injection when necessary."""
    # Reset static cache to avoid cross-test interference
    CronPatch._MODULAR_STATE_CACHE.clear()
    
    # 1. Setup mock environment
    store_path = tmp_path / "jobs.json"
    store_path.write_text("{}") # Empty jobs.json
    
    # Mock modular jobs
    with patch("strategery.patches.batch.strategic_load_modular_jobs") as mock_load:
        
        # Point context to our tmp storage
        mock_context.storage_root = tmp_path / "storage"
        items_dir = mock_context.storage_root / "workspace" / "cron" / "items"
        items_dir.mkdir(parents=True, exist_ok=True)
        
        mock_load.return_value = [] # Return empty jobs list

        # 2. Apply patch and instantiate service
        patch_obj = CronPatch()
        patch_obj.apply(mock_context)
        service = CronService(store_path)
        
        # 3. FIRST LOAD
        # Force a reload by setting _store to None
        service._store = None
        # We need to ensure the patched context is available globally during execution
        with patch("strategery.patches.config.load_strategic_context", return_value=(mock_context.config, mock_context.user_email, mock_context.storage_root)):
            service._load_store()
            assert mock_load.call_count == 1, "Should load modular jobs on first load"
            
            # 4. SECOND LOAD (No changes)
            # Manually sync the service's tracking stats to the file on disk
            stat = store_path.stat()
            service._last_mtime = stat.st_mtime
            service._last_size = stat.st_size
            
            # Reset the mock to start fresh for the second check
            mock_load.reset_mock()
            
            service._load_store()
            assert mock_load.call_count == 0, "Should NOT load modular jobs again if nothing changed"
            
            # 5. MODULAR JOBS CHANGE (Simulate)
            # Create a dummy .md file to change the items directory state
            dummy_file = items_dir / "job1.md"
            dummy_file.write_text("dummy")
            
            # 6. THIRD LOAD (With changes)
            service._load_store()
            assert mock_load.call_count == 1, "Should reload modular jobs after a change in items directory"

            # 7. FOURTH LOAD (No further changes)
            mock_load.reset_mock()
            service._load_store()
            assert mock_load.call_count == 0, "Should NOT reload modular jobs again"
