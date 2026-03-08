import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from nanobot.agent.loop import AgentLoop
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.providers.base import LLMProvider
from strategery.patches.subagent import SubagentPatch
from strategery.patches.loop import AgentLoopPatch

class BehavioralMockProvider(LLMProvider):
    """A mock provider that returns predefined tool calls to simulate behavioral flows."""
    def __init__(self, tool_calls=None, content="Mock response"):
        self.tool_calls = tool_calls or []
        self.content = content
        self._last_model = None

    async def chat(self, messages, tools=None, model=None, **kwargs):
        self._last_model = model
        mock_response = MagicMock()
        mock_response.content = self.content
        mock_response.has_tool_calls = len(self.tool_calls) > 0
        mock_response.tool_calls = self.tool_calls
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

    async def run_prompt(self, prompt, mock_tool_calls=None, role="main"):
        """Runs the agent loop with a mock provider and captures behavior."""
        provider = BehavioralMockProvider(tool_calls=mock_tool_calls)
        
        # 1. Apply Strategic Patches to the classes before instantiation
        # (This ensures the Strategic Registry and Spawner are active)
        SubagentPatch().apply(self.config)
        AgentLoopPatch().apply(self.config)
        
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
        
        # 4. Patch the subagents manager and registry to capture behavior
        loop.subagents.spawn = AsyncMock(side_effect=self._mock_spawn)
        
        orig_execute = loop.tools.execute
        async def patched_execute(name, arguments, **kwargs):
            self.captured_tools.append({"name": name, "args": arguments})
            return await orig_execute(name, arguments, **kwargs)
        
        loop.tools.execute = patched_execute
        
        # 4. Build context and run one iteration of the loop
        from nanobot.bus.events import InboundMessage
        from nanobot.session.manager import Session
        msg = InboundMessage(channel="test", chat_id="user1", content=prompt, sender_id="user1")
        
        # Use ContextBuilder to build messages
        context = loop.context.build_messages(
            history=[],
            current_message=msg.content,
            channel=msg.channel,
            chat_id=msg.chat_id
        )
        
        # Call provider (Simulating AgentLoop._process_message)
        response = await provider.chat(
            messages=context, 
            tools=loop.tools.get_definitions(),
            model=loop.model
        )
        
        # Execute tool calls if any
        executed_tool_results = []
        if response.has_tool_calls:
            for tc in response.tool_calls:
                res = await loop.tools.execute(tc["function"]["name"], tc["function"]["arguments"])
                executed_tool_results.append({"name": tc["function"]["name"], "result": res})
        
        # Identify the system prompt from context
        system_prompt = next((m["content"] for m in context if m["role"] == "system"), "")

        return {
            "model_used": provider._last_model,
            "spawns": self.captured_spawns,
            "tools": self.captured_tools,
            "tool_results": executed_tool_results,
            "available_tools": [d["function"]["name"] for d in loop.tools.get_definitions()],
            "system_prompt": system_prompt
        }
