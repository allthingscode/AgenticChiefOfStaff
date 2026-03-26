import asyncio
from unittest.mock import AsyncMock, MagicMock

from nanobot.agent.subagent import SubagentManager
from strategery.patches import registry
from strategery.patches.base import PatchContext
from strategery.patches.config import load_strategic_context


async def test_subagent_model_routing():
    """Verify that a spawned subagent uses the correct model from config."""
    print("--- Subagent Model Routing Verification ---")

    # 1. Load Context & Apply Patches
    raw_cfg, email, root = load_strategic_context()
    PatchContext(config=raw_cfg, storage_root=root, user_email=email, app_root=".")
    registry.apply_all(raw_cfg, storage_root=root, user_email=email)

    # 2. Setup SubagentManager mock
    # We need a provider that returns a mock response
    mock_provider = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Verified model routing."
    mock_response.has_tool_calls = False
    mock_provider.chat = AsyncMock(return_value=mock_response)

    sub_mgr = SubagentManager(
        provider=mock_provider,
        model="gemini-3-flash-preview",
        workspace=root / "workspace",
        bus=MagicMock()
    )
    sub_mgr.bus.publish_inbound = AsyncMock()

    # 3. Trigger Spawn
    # This will call the patched _run_subagent (from CheckpointPatch)
    task_id = "test-routing"
    task = "Verify your model."
    label = "Model Test"
    origin = {"channel": "cli", "chat_id": "direct"}

    print("Spawning subagent with specialist='researcher'...")
    # Directly call the patched _run_subagent to observe the model selection
    await SubagentManager._run_subagent(sub_mgr, task_id, task, label, origin, specialist="researcher")

    # 4. Assert
    # Check the last call to provider.chat
    chat_args = mock_provider.chat.call_args
    if chat_args:
        actual_model = chat_args.kwargs.get("model")
        print(f"Actual model used in chat: {actual_model}")

        expected_model = "gemini-2.5-flash-lite" # From config.json researcher
        if actual_model == expected_model:
            print("SUCCESS: Subagent routed to correct specialist model.")
        else:
            print(f"FAILED: Expected {expected_model}, got {actual_model}")
    else:
        print("FAILED: provider.chat was never called.")

if __name__ == "__main__":
    asyncio.run(test_subagent_model_routing())
