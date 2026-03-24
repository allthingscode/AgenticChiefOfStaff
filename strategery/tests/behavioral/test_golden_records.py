import pytest
import json
import asyncio
from pathlib import Path
from strategery.tests.behavioral.simulator import StrategicSimulator

def load_golden_records():
    records_dir = Path(__file__).parent / "records"
    records = []
    for file in records_dir.glob("*.json"):
        with open(file, "r", encoding="utf-8") as f:
            records.append(json.load(f))
    return records

@pytest.mark.asyncio
@pytest.mark.parametrize("record", load_golden_records(), ids=lambda r: r["id"])
async def test_behavioral_snapshot(record):
    """
    Executes a behavioral snapshot (Golden Record) and asserts expectations.
    """
    # 1. Initialize Simulator
    # We use a minimal mock config for the specialists
    config_data = {
        "agents": {
            "specialists": {
                "researcher": {"model": "researcher-model", "keywords": ["research", "health"]},
                "architect": {"model": "architect-model", "keywords": ["design", "plan"]}
            }
        }
    }
    simulator = StrategicSimulator(config_data)

    # 2. Run the prompt through the simulator
    results = await simulator.run_prompt(
        prompt=record["input"],
        mock_tool_calls=record.get("mock_tool_calls"),
        role=record.get("role", "main"), mock_content="" if record.get("expectations", {}).get("progress_suppressed", False) else "Mock response"
    )

    # 3. Assert Expectations
    exp = record.get("expectations", {})

    # A. Tool Visibility (Mandate Enforcement)
    for forbidden in exp.get("forbidden_tools", []):
        assert forbidden not in results["available_tools"], f"Mandate Violation: Forbidden tool '{forbidden}' is visible to the model."

    for required in exp.get("required_tools", []):
        assert required in results["available_tools"], f"Logic Failure: Required tool '{required}' is NOT visible to the model."

    # B. Execution Behavior (Specialist Routing)
    if "specialist" in exp:
        found_specialist = False
        for spawn in results["spawns"]:
            if spawn.get("specialist") == exp["specialist"]:
                found_specialist = True
                break
        assert found_specialist, f"Routing Failure: Expected specialist '{exp['specialist']}' was not spawned."

    # C. Task Content Verification
    for substring in exp.get("subagent_task_contains", []):
        found_substring = False
        for spawn in results["spawns"]:
            if substring.lower() in spawn["task"].lower():
                found_substring = True
                break
        assert found_substring, f"Content Failure: Subagent task did not contain expected keyword '{substring}'."

    # D. Tool Call Verification
    for tool_name in exp.get("executed_tools", []):
        found_tool = False
        for tool in results["tools"]:
            if tool["name"] == tool_name:
                found_tool = True
                break
        assert found_tool, f"Execution Failure: Expected tool '{tool_name}' was not called."

    # E. Tool Result Verification (Mandates in tool output)
    for substring in exp.get("tool_result_contains", []):
        found_substring = False
        for res_content in results["tool_results"]:
            if substring.lower() in res_content.lower():
                found_substring = True
                break
        assert found_substring, f"Mandate Failure: Tool result did not contain expected directive '{substring}'."

    # F. System Prompt Verification
    for substring in exp.get("prompt_contains", []):
        assert substring.lower() in results["system_prompt"].lower(), f"Prompt Failure: System prompt missing mandatory directive '{substring}'."

    for substring in exp.get("prompt_excludes", []):
        assert substring.lower() not in results["system_prompt"].lower(), f"Prompt Failure: System prompt contains forbidden directive '{substring}'."

    # G. Progress Suppression Verification (Silent Spawn)
    if exp.get("progress_suppressed", False):
        # In a Silent Spawn, the progress updates (thoughts/hints) should NOT contain 'spawn' or any content
        # unless it's the final turn which is handled by _run_agent_loop's return.
        for progress in results["captured_progress"]:
            content = progress.get("content", "")
            # We allow tool hints (e.g. "Executing spawn...") if they are specifically exempted, 
            # but usually we want to suppress everything for spawn turns.
            if content and not (content.startswith("spawn(") and content.endswith(")")):
                assert not content, f"Progress Failure: Progress content was not suppressed during spawn turn: {content}"

    # H. Final Content Verification
    for substring in exp.get("final_content_contains", []):
        assert substring.lower() in results["final_content"].lower(), f"Content Failure: Final content did not contain expected keyword '{substring}'."
