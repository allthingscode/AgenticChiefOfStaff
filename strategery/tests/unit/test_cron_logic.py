from unittest.mock import MagicMock
from strategery.logic import cron_logic

def test_should_reload_jobs_mtime():
    assert cron_logic.should_reload_jobs(200.0, 100.0, 50, 50) is True

def test_should_reload_jobs_size():
    assert cron_logic.should_reload_jobs(100.0, 100.0, 100, 50) is True

def test_should_reload_jobs_none():
    assert cron_logic.should_reload_jobs(100.0, 100.0, 50, 50) is False

def test_merge_modular_jobs_new():
    existing = [MagicMock(id="job1")]
    new_jobs = [MagicMock(id="batch_job2")]
    merged = cron_logic.merge_modular_jobs(existing, new_jobs, {})
    assert len(merged) == 2
    assert merged[1].id == "batch_job2"

def test_merge_modular_jobs_update():
    # Use real objects instead of mocks for the update test to avoid identity confusion
    class JobMock:
        def __init__(self, id, name, schedule=None, payload=None):
            self.id = id
            self.name = name
            self.schedule = schedule
            self.payload = payload
            self.state = {}

    old_job = JobMock("batch_job1", "Old")
    new_job = JobMock("batch_job1", "New", "0 3 * * *", {"msg": "hello"})
    
    merged = cron_logic.merge_modular_jobs([old_job], [new_job], {})
    assert len(merged) == 1
    assert merged[0].name == "New"
    assert merged[0].schedule == "0 3 * * *"
    assert merged[0].payload == {"msg": "hello"}

def test_cache_modular_state():
    job1 = MagicMock(id="batch_job1", state="running")
    job2 = MagicMock(id="other", state="idle")
    cache = cron_logic.cache_modular_state([job1, job2])
    assert "batch_job1" in cache
    assert cache["batch_job1"] == "running"
    assert "other" not in cache
