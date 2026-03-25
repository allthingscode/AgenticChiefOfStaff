import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from nanobot.agent.loop import AgentLoop
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.providers.base import LLMProvider
from strategery.patches.subagent import SubagentPatch
from strategery.patches.loop import AgentLoopPatch

from nanobot.providers.base import LLMProvider, ToolCallRequest

class BehavioralMockProvider(LLMProvider):
    """A mock provider that returns predefined tool calls to simulate behavioral flows."""
    def __init__(self, tool_calls=None, content="Mock response"):
        self.tool_calls = tool_calls or []
        self.content = content
        self._last_model = None
        self._calls_returned = False

    async def chat(self, messages, tools=None, model=None, **kwargs):
        self._last_model = model
        
        # Convert dictionary tool calls to ToolCallRequest objects
        requests = []
        # ONLY return tool calls on the FIRST call to chat in this turn
        if not self._calls_returned:
            for tc in self.tool_calls:
                if isinstance(tc, dict):
                    requests.append(ToolCallRequest(
                        id=tc.get("id", "mock-id"),
                        name=tc.get("function", {}).get("name", tc.get("name")),
                        arguments=tc.get("function", {}).get("arguments", tc.get("arguments", {}))
                    ))
                else:
                    requests.append(tc)
            self._calls_returned = True

        mock_response = MagicMock()
        mock_response.content = self.content
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
        # We capture what's passed to SubagentManager.spawn (as patched by SubagentPatch)
        self.captured_spawns.append({
            "task": task, 
            "label": label, 
            "specialist": kwargs.get("specialist")
        })
        return f"mock-subagent-{len(self.captured_spawns)}"

    async def run_prompt(self, prompt, mock_tool_calls=None, role="main", specialist_type="researcher", mock_content="Mock response", mock_tool_results=None):
        """Runs the agent loop with a mock provider and captures behavior."""
        provider = BehavioralMockProvider(tool_calls=mock_tool_calls, content=mock_content)
        mock_results = mock_tool_results or {}
        
        # 1. Apply Strategic Patches to the classes before instantiation
        # (This ensures the Strategic Registry and Spawner are active)
        from strategery.patches.base import PatchContext
        from strategery.patches.config import load_strategic_context, ConfigPatch
        from strategery.patches.loop import AgentLoopPatch
        from strategery.patches.subagent import SubagentPatch
        
        # Build a proper context for the patches
        raw_config, email, storage = load_strategic_context()
        # MANDATE: Use dynamic resolution for app_root to avoid personal hard-coded paths.
        project_root = Path(__file__).parent.parent.parent.parent.absolute()
        context = PatchContext(
            config=self.config, # Mock config passed in
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
        
        # 3. Setup Tool Registry based on Role (BUG-053/054)
        if role == "specialist":
            loop.tools._is_strategic_specialist = True
            loop.subagents._strategic_specialist_type = specialist_type
        
        # Register dummy tools for visibility checks
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
        
        # Add basic tools that are normally present
        from nanobot.agent.tools.shell import ExecTool
        from nanobot.agent.tools.filesystem import ReadFileTool, ListDirTool
        loop.tools.register(ExecTool())
        loop.tools.register(ReadFileTool())
        loop.tools.register(ListDirTool())
        
        # 4. Patch the subagents manager and registry to capture behavior
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
        
        # 4. Build context
        from nanobot.bus.events import InboundMessage
        msg = InboundMessage(channel="test", chat_id="user1", content=prompt, sender_id="user1")
        
        # We need to ensure the system prompt is built using our specialist_type if role=specialist
        if role == "specialist":
            # The context builder build_messages will call inject_delegation_mandate (for main)
            # But here we are simulating a specialist turn directly.
            # We must monkeypatch build_messages or the prompt builder.
            pass

        context = loop.context.build_messages(
            history=[],
            current_message=msg.content,
            channel=msg.channel,
            chat_id=msg.chat_id
        )
        
        if role == "specialist":
            # Override system prompt for specialist
            for m in context:
                if m["role"] == "system":
                    from strategery.logic import subagent_logic
                    m["content"] = subagent_logic.build_specialist_instructions(m["content"], specialist_type)

        # 5. Run the full agent loop (supporting multiple iterations)
        # We need to capture the tool results manually since we're calling _run_agent_loop
        final_content, tools_used, all_msgs = await loop._run_agent_loop(
            context, on_progress=mock_on_progress
        )
        
        # Identify the system prompt from context
        system_prompt = next((m["content"] for m in context if m["role"] == "system"), "")

        # Extract tool results from all_msgs
        tool_results = [m["content"] for m in all_msgs if m.get("role") == "tool"]

        return {
            "model_used": provider._last_model,
            "spawns": self.captured_spawns,
            "tools": self.captured_tools,
            "tool_results": tool_results,
            "available_tools": [d["function"]["name"] for d in loop.tools.get_definitions()],
            "system_prompt": system_prompt,
            "captured_progress": captured_progress,
            "final_content": final_content
        }
