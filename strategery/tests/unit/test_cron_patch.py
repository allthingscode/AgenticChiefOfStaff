import pytest
from nanobot.cron.service import CronService
from nanobot.cron.types import CronSchedule
from strategery.patches.cron import CronPatch

@pytest.mark.asyncio
async def test_cron_patch_logic(tmp_path):
    """Verify that CronPatch logic triggers reload on size change even if mtime is identical."""
    # 1. Setup
    store_path = tmp_path / "jobs.json"
    service = CronService(store_path)
    
    # Apply patch
    patch = CronPatch()
    patch.apply({})
    
    # 2. Create initial file
    service.add_job(
        name="initial",
        schedule=CronSchedule(kind="every", every_ms=10000),
        message="hello"
    )
    
    # Load it once
    service._load_store()
    initial_size = service._last_size
    assert initial_size > 0

    # 3. MANUALLY simulate a size change with identical mtime
    # We don't rely on the filesystem here, we just test the logic of the patched method
    import json
    data = json.loads(store_path.read_text())
    data["jobs"][0]["name"] = "updated"
    new_content = json.dumps(data, indent=4) # Indent ensures size change
    store_path.write_text(new_content)
    
    new_size = store_path.stat().st_size
    assert new_size != initial_size
    
    # We FORCE mtime to be the same in the service state to test our patch
    service._last_mtime = store_path.stat().st_mtime 
    service._last_size = initial_size # Keep old size to trigger reload
    
    # 4. TEST: The patched service should see that size is different and reload
    reloaded_store = service._load_store()
    assert reloaded_store.jobs[0].name == "updated"
    assert service._last_size == new_size
