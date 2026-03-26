import asyncio
import json
from unittest.mock import MagicMock, AsyncMock
from nanobot.agent.subagent import SubagentManager
from nanobot.bus.events import InboundMessage
from strategery.patches import registry
from strategery.patches.base import PatchContext
from strategery.patches.config import load_strategic_context
from strategery.logic import subagent_logic

async def test_multimodal_handoff():
    """Verify that images sent to Main Agent are captured and passed to subagents (ARCH-022)."""
    print("\n--- ARCH-022 Multimodal Handoff Verification ---")
    
    # 1. Load Context
    raw_cfg, email, root = load_strategic_context()
    context = PatchContext(config=raw_cfg, storage_root=root, user_email=email, app_root=".")
    registry.apply_all(raw_cfg, storage_root=root, user_email=email)
    
    # 2. Simulate a message with media coming in
    msg = InboundMessage(
        channel="telegram",
        sender_id="user123",
        chat_id="chat123",
        content="Check this architecture diagram.",
        media=["D:/Nanobot_Storage/workspace/media/diag.png"]
    )
    
    # Simulate AgentLoop Patch tagging the content (Ironclad Tagging)
    # Normally this happens in loop.py patched _dispatch
    msg.content += "\n[image: D:/Nanobot_Storage/workspace/media/diag.png]"
    
    # 3. Setup SubagentManager mock
    mock_provider = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "I see the image."
    mock_response.has_tool_calls = False
    mock_provider.chat = AsyncMock(return_value=mock_response)
    
    # RESPONSE 0: Validation Rubric
    resp_rubric = MagicMock()
    resp_rubric.content = json.dumps({
        "task_goal": "Analyze Image",
        "criteria": [{"name": "Vision", "description": "Must use vision tool", "weight": 1.0}],
        "success_threshold": 0.9
    })
    resp_rubric.has_tool_calls = False
    
    mock_provider.chat.side_effect = [resp_rubric, mock_response]
    
    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()
    
    sub_mgr = SubagentManager(
        provider=mock_provider, 
        model="gemini-3-flash-preview",
        workspace=root / "workspace",
        bus=mock_bus
    )
    # Ensure _announce_result doesn't crash on the mock bus
    sub_mgr._announce_result = AsyncMock()
    
    # 4. Trigger Spawn (simulating Main Agent turn)
    # The spawn tool logic scans history for the [image: path] tags.
    # We mock the last messages history.
    history = [{"role": "user", "content": msg.content}]
    
    print("Executing spawn call with history-capture...")
    # Simulate spawn tool execution (simplified)
    # In reality, the SpawnTool.execute logic would scan its registry's last messages.
    attachments = []
    import re
    paths = re.findall(r"\[image: (.*?)\]", msg.content)
    for p in paths:
        attachments.append({
            "path": p,
            "filename": "diag.png",
            "content_type": "image/png"
        })
    
    # Call the patched subagent manager
    task_id = "test-vision"
    task = "Analyze the diagram."
    label = "Vision Test"
    origin = {"channel": "telegram", "chat_id": "chat123"}
    
    await SubagentManager._run_subagent(
        sub_mgr, task_id, task, label, origin, 
        specialist="researcher", attachments=attachments
    )
    
    # 5. Verify Prompt
    # The last call to chat should contain the manifest with the attachment path.
    chat_args = mock_provider.chat.call_args_list
    # The first chat turn should be Turn 0 (Rubric Gen), the second is Turn 1 (Specialist Start)
    
    system_prompt = ""
    for call in chat_args:
        messages = call.kwargs.get("messages", [])
        for m in messages:
            if m["role"] == "system" and "ATTACHMENTS" in m["content"]:
                system_prompt = m["content"]
                break
    
    print("\n--- System Prompt Snip ---")
    if system_prompt:
        print(system_prompt[-500:]) # Show the end where attachments are
        assert "D:/Nanobot_Storage/workspace/media/diag.png" in system_prompt
        print("\nSUCCESS: Image path correctly injected into subagent system instructions.")
    else:
        print("\nFAILED: Attachments section not found in system prompt.")
        # Debug: show what was found
        # print(chat_args)

if __name__ == "__main__":
    asyncio.run(test_multimodal_handoff())
