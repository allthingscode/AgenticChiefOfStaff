import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

from strategery.logic import subagent_logic
from strategery.patches.config import load_strategic_context


async def test_rubric_reflection_loop():
    """Verify end-to-end reflection loop: Rubric -> Fail -> Critic -> Refine -> Success."""
    print("\n--- F-031 Rubric Reflection Loop Verification ---")

    # 1. Load Context
    raw_cfg, email, root = load_strategic_context()
    # context = PatchContext(config=raw_cfg, storage_root=root, user_email=email, app_root=".")

    # 2. Setup Mock Provider with sequenced responses
    mock_provider = MagicMock()

    # RESPONSE 0: Validation Rubric
    resp_rubric = MagicMock()
    resp_rubric.content = json.dumps({
        "task_goal": "Test Reflection",
        "criteria": [{"name": "Execution", "description": "Must do work", "weight": 1.0}],
        "success_threshold": 0.9
    })
    resp_rubric.has_tool_calls = False

    # RESPONSE 1: Incomplete Answer (Fail) - Triggers BUG-252 nudge
    resp_fail = MagicMock()
    resp_fail.content = "I plan to test this later."
    resp_fail.has_tool_calls = False

    # RESPONSE 2: Still failing after nudge
    resp_fail_again = MagicMock()
    resp_fail_again.content = "Still just a plan."
    resp_fail_again.has_tool_calls = False

    # RESPONSE 3: Critic Report (Scoring Failure)
    resp_critic = MagicMock()
    resp_critic.content = json.dumps({
        "overall_score": 0.2,
        "scores": [{"criterion_name": "Execution", "score": 0.2, "reasoning": "Did nothing."}],
        "passed": False,
        "feedback": "You didn't do the task.",
        "required_corrections": ["Actually perform the test"]
    })
    resp_critic.has_tool_calls = False

    # RESPONSE 4: Final Corrected Answer
    resp_success = MagicMock()
    resp_success.content = "Task successfully executed after refinement."
    resp_success.has_tool_calls = False

    # Sequence of responses
    mock_provider.chat = AsyncMock(side_effect=[
        resp_rubric,      # Turn 0 (Rubric Gen)
        resp_fail,        # Turn 1 (Specialist Output -> triggers nudge)
        resp_fail_again,  # Turn 2 (Specialist Output after nudge)
        resp_critic,      # Turn 3 (Critic Audit)
        resp_success      # Turn 4 (Refinement Output)
    ])

    # 3. Setup Orchestration Params
    task_id = "test-reflection"
    task = "Please test the reflection loop."
    messages = [{"role": "system", "content": "Base prompt"}]
    tools = MagicMock()
    tools.get_definitions.return_value = []

    # 4. Run Loop
    print("Running orchestration loop with mock provider...")
    result = await subagent_logic.run_orchestration_loop(
        task_id=task_id,
        task=task,
        messages=messages,
        provider=mock_provider,
        model="gemini-3-pro-preview",
        tools=tools,
        temperature=0.0,
        max_tokens=1000,
        reasoning_effort="medium"
    )

    # 5. Assertions
    print(f"Final Result: {result}")

    # We expect 4 calls to chat (Rubric, Initial, Critic, Refinement)
    call_count = mock_provider.chat.call_count
    print(f"Total Chat Turns: {call_count}")

    assert call_count >= 4, f"Expected at least 4 turns, got {call_count}"
    assert "refinement" in result.lower(), "Result did not show evidence of refinement."

    # Verify Critic message was injected into history
    critic_injected = any("### 🛡️ CRITIC AUDIT FAILED" in str(m.get("content")) for m in messages)
    assert critic_injected, "Critic feedback was not found in message history."

    print("SUCCESS: Rubric Reflection Loop verified end-to-end.")

if __name__ == "__main__":
    asyncio.run(test_rubric_reflection_loop())
