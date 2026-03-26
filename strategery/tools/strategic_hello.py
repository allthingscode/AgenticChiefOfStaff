from typing import Any

from nanobot.agent.tools.base import Tool


class StrategicHelloTool(Tool):
    """A simple tool to verify the strategic tool registry."""

    @property
    def name(self) -> str:
        return "strategic_hello"

    @property
    def description(self) -> str:
        return "Returns a friendly greeting to verify strategic side-loading."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the person to greet."
                }
            },
            "required": ["name"]
        }

    async def execute(self, **kwargs: Any) -> str:
        name = kwargs.get("name", "Stranger")
        return f"Hello, {name}! The Strategic Tool Registry is operational."
