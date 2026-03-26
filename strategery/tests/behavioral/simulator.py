from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from nanobot.agent.loop import AgentLoop
from nanobot.providers.base import LLMProvider, ToolCallRequest
from strategery.patches.loop import AgentLoopPatch
from strategery.patches.subagent import SubagentPatch


class BehavioralMockProvider(LLMProvider):
    """
    A mock provider that supports multi-turn scenarios.
    It iterates through a list of 'turns', each providing content and tool calls.
    """
    def __init__(self, turns=None, content="Mock response", tool_calls=None):
        self.turns = turns or [{"content": content, "tool_calls": tool_calls or []}]
        self.current_turn = 0
        self._last_model = None

    async def chat(self, messages, tools=None, model=None, **kwargs):
        self._last_model = model

        if self.current_turn >= len(self.turns):
            # Fallback for unexpected extra turns
            mock_response = MagicMock()
            mock_response.content = "No more turns defined in scenario."
            mock_response.has_tool_calls = False
            mock_response.tool_calls = []
            return mock_response

        turn_data = self.turns[self.current_turn]
        self.current_turn += 1

        requests = []
        mock_tool_calls = turn_data.get("tool_calls", [])
        for tc in mock_tool_calls:
            if isinstance(tc, dict):
                requests.append(ToolCallRequest(
                    id=tc.get("id", f"mock-id-{self.current_turn}"),
                    name=tc.get("function", {}).get("name", tc.get("name")),
                    arguments=tc.get("function", {}).get("arguments", tc.get("arguments", {}))
                ))
            else:
                requests.append(tc)

        mock_response = MagicMock()
        mock_response.content = turn_data.get("content", "")
        mock_response.has_tool_calls = len(requests) > 0
        mock_response.tool_calls = requests
        mock_response.finish_reason = "stop"
        mock_response.reasoning_content = None
        mock_response.thinking_blocks = None
        return mock_response

    def get_default_model(self) -> str:
        return "mock-default-model"

    async def embed(self, texts, **kwargs):
        return [[0.1] * 1536 for _ in texts]

class StrategicSimulator:
    """Harness to run AgentLoop in a controlled behavioral test environment."""
    def __init__(self, config_data):
        self.config = config_data
        self.captured_spawns = []
        self.captured_tools = []

    def _mock_spawn(self, task, label=None, **kwargs):
        self.captured_spawns.append({
            "task": task,
            "label": label,
            "specialist": kwargs.get("specialist")
        })
        return f"mock-subagent-{len(self.captured_spawns)}"

    async def run_prompt(self, prompt, mock_tool_calls=None, role="main", specialist_type="researcher",
                         mock_content="Mock response", mock_tool_results=None, turns=None):
        """
        Runs the agent loop with a mock provider and captures behavior.
        Supports single-turn (backwards compatibility) or multi-turn scenarios via 'turns'.
        """
        if turns:
            # Multi-turn scenario
            provider = BehavioralMockProvider(turns=turns)
            # Consolidate all mock results from all turns
            mock_results = {}
            for turn in turns:
                mock_results.update(turn.get("tool_results", {}))
        else:
            # Single-turn (compat mode)
            provider = BehavioralMockProvider(content=mock_content, tool_calls=mock_tool_calls)
            mock_results = mock_tool_results or {}

        # 1. Apply Strategic Patches
        from strategery.patches.base import PatchContext
        from strategery.patches.config import ConfigPatch, load_strategic_context

        raw_config, email, storage = load_strategic_context()
        project_root = Path(__file__).parent.parent.parent.parent.absolute()
        context = PatchContext(
            config=self.config,
            storage_root=storage,
            user_email=email,
            app_root=project_root
        )

        SubagentPatch().apply(context)
        AgentLoopPatch().apply(context)
        ConfigPatch().apply(context)

        # 2. Setup AgentLoop with mocks
        with patch("strategery.patches.config.load_strategic_context", return_value=(None, "test@example.com", Path("/tmp/storage"))):
            loop = AgentLoop(
                bus=AsyncMock(),
                provider=provider,
                workspace=Path("/tmp/workspace"),
                session_manager=MagicMock()
            )

        # 3. Setup Tool Registry based on Role
        if role == "specialist":
            loop.tools._is_strategic_specialist = True
            loop.subagents._strategic_specialist_type = specialist_type

        # Register dummy tools
        from nanobot.agent.tools.base import Tool
        class MockSurgicalTool(Tool):
            @property
            def name(self): return "mcp_google-ai-search_search_ai"
            @property
            def description(self): return "Mock Tool"
            @property
            def parameters(self): return {"type": "object", "properties": {}}
            async def execute(self, **kwargs): return "Mock result"

        loop.tools.register(MockSurgicalTool())

        from nanobot.agent.tools.filesystem import ListDirTool, ReadFileTool
        from nanobot.agent.tools.shell import ExecTool
        loop.tools.register(ExecTool())
        loop.tools.register(ReadFileTool())
        loop.tools.register(ListDirTool())

        # 4. Patch behaviors
        loop.subagents.spawn = AsyncMock(side_effect=self._mock_spawn)

        captured_progress = []
        async def mock_on_progress(content, **kwargs):
            captured_progress.append({"content": content, **kwargs})

        orig_execute = loop.tools.execute
        async def patched_execute(name, arguments, **kwargs):
            self.captured_tools.append({"name": name, "args": arguments})
            if name in mock_results:
                return mock_results[name]
            return await orig_execute(name, arguments, **kwargs)

        loop.tools.execute = patched_execute

        # 5. Build context
        from nanobot.bus.events import InboundMessage
        msg = InboundMessage(channel="test", chat_id="user1", content=prompt, sender_id="user1")

        context = loop.context.build_messages(
            history=[],
            current_message=msg.content,
            channel=msg.channel,
            chat_id=msg.chat_id
        )

        if role == "specialist":
            for m in context:
                if m["role"] == "system":
                    from strategery.logic import subagent_logic
                    m["content"] = subagent_logic.build_specialist_instructions(m["content"], specialist_type)

        # 6. Run the loop
        final_content, tools_used, all_msgs = await loop._run_agent_loop(
            context, on_progress=mock_on_progress
        )

        system_prompt = next((m["content"] for m in context if m["role"] == "system"), "")
        tool_results = [m["content"] for m in all_msgs if m.get("role") == "tool"]

        return {
            "model_used": provider._last_model,
            "spawns": self.captured_spawns,
            "tools": self.captured_tools,
            "tool_results": tool_results,
            "available_tools": [d["function"]["name"] for d in loop.tools.get_definitions()],
            "system_prompt": system_prompt,
            "captured_progress": captured_progress,
            "final_content": final_content,
            "all_messages": all_msgs
        }
