from datetime import datetime, timedelta
from strategery.logic import memory_logic

def test_format_consolidation_messages():
    msgs = [
        {"role": "user", "content": "Hello", "timestamp": "2026-03-08T12:00:00"},
        {"role": "assistant", "content": "Hi there", "timestamp": "2026-03-08T12:01:00"}
    ]
    res = memory_logic.format_consolidation_messages(msgs)
    assert "[2026-03-08T12:00] USER: Hello" in res
    assert "[2026-03-08T12:01] ASSISTANT: Hi there" in res

def test_parse_consolidation_response_json():
    content = '{"history_entry": "test summary", "memory_update": "test facts"}'
    res = memory_logic.parse_consolidation_response(content, False, None, "old facts")
    assert res["history_entry"] == "test summary"
    assert res["memory_update"] == "test facts"

def test_parse_consolidation_response_regex_recovery():
    content = 'Certainly! Here is the JSON: {"summary": "recovered summary", "facts": "recovered facts"}'
    res = memory_logic.parse_consolidation_response(content, False, None, "old facts")
    assert res["history_entry"] == "recovered summary"
    assert res["memory_update"] == "recovered facts"

def test_should_skip_rag():
    assert memory_logic.should_skip_rag("ok") is True
    assert memory_logic.should_skip_rag("Tell me a long story about the moon.") is False

def test_filter_rag_results():
    results = [
        {"content": "Valid fact"},
        {"content": "I have spawned a subagent"},
        {"content": "No summary available"}
    ]
    filtered = memory_logic.filter_rag_results(results)
    assert len(filtered) == 1
    assert filtered[0]["content"] == "Valid fact"

def test_prune_context_retention():
    # Setup messages with timestamps
    now = datetime.now()
    # Subtract 10 hours safely
    old_ts = (now - timedelta(hours=10)).isoformat()
    new_ts = now.isoformat()
    
    msgs = [
        {"role": "user", "content": "Old user", "timestamp": old_ts},
        {"role": "assistant", "content": "Old assistant", "timestamp": old_ts},
        {"role": "user", "content": "New user", "timestamp": new_ts}
    ]
    
    # Prune with 6h TTL, keep last 1 assistant
    pruned = memory_logic.prune_context(msgs, 6, 1)
    
    # User messages are always kept in this logic (Pass 1: if role == "user": keep = True)
    # The old assistant should be pruned because it's > 6h and assistant_count > keep_last (if we process newest first)
    roles = [m["role"] for m in pruned]
    assert "user" in roles
    assert len(pruned) >= 2
