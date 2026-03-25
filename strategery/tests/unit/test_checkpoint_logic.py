import pytest
from strategery.logic.checkpoint_logic import get_checkpoint_manager

@pytest.fixture
def temp_storage(tmp_path):
    storage = tmp_path / "storage"
    storage.mkdir()
    (storage / "workspace").mkdir()
    return str(storage)

def test_checkpoint_lifecycle(temp_storage):
    manager = get_checkpoint_manager(temp_storage)
    thread_id = "test-session-1"
    
    # 1. Create Thread
    manager.create_thread(thread_id, "gemini-3-flash", {"temp": 0.1})
    
    # 2. Save Snapshots
    messages_1 = [{"role": "user", "content": "Hello"}]
    assert manager.save_snapshot(thread_id, 1, messages_1) is True
    
    messages_2 = messages_1 + [{"role": "assistant", "content": "Hi there!"}]
    assert manager.save_snapshot(thread_id, 2, messages_2) is True
    
    # 3. Load Latest
    latest = manager.load_latest(thread_id)
    assert latest is not None
    assert latest["iteration"] == 2
    assert len(latest["messages"]) == 2
    assert latest["messages"][1]["content"] == "Hi there!"
    assert latest["model"] == "gemini-3-flash"
    
    # 4. List Resumable
    resumable = manager.list_resumable()
    assert len(resumable) == 1
    assert resumable[0]["thread_id"] == thread_id
    
    # 5. Complete Thread
    manager.complete_thread(thread_id)
    resumable_after = manager.list_resumable()
    assert len(resumable_after) == 0

def test_complex_message_serialization(temp_storage):
    manager = get_checkpoint_manager(temp_storage)
    thread_id = "test-complex"
    
    complex_messages = [
        {
            "role": "assistant", 
            "content": None, 
            "tool_calls": [{
                "id": "c1", 
                "type": "function", 
                "function": {"name": "test", "arguments": "{}"}
            }]
        },
        {
            "role": "tool",
            "tool_call_id": "c1",
            "name": "test",
            "content": "result"
        }
    ]
    
    assert manager.save_snapshot(thread_id, 1, complex_messages) is True
    restored = manager.load_latest(thread_id)
    assert restored["messages"][0]["tool_calls"][0]["id"] == "c1"
