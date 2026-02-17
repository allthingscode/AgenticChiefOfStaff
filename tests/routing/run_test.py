
import asyncio
import sys
from pathlib import Path

# Add project root to the Python path to allow importing nanobot
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from nanobot.config.loader import load_config
from nanobot.agent.loop import AgentLoop
from nanobot.providers.litellm_provider import LiteLLMProvider
from nanobot.bus.queue import MessageBus
from loguru import logger

# Ensure logs are written for verification, but disable console output to keep the test clean
logger.remove()
logger.add(sys.stderr, level="INFO")
log_file_path = Path.home() / ".nanobot" / "logs" / "nanobot.log"
log_file_path.parent.mkdir(parents=True, exist_ok=True)
logger.add(log_file_path, rotation="10 MB", level="DEBUG")

def _make_provider(config):
    """Helper function to create LiteLLMProvider from config."""
    from nanobot.providers.litellm_provider import LiteLLMProvider
    p = config.get_provider()
    model = config.agents.defaults.model
    if not (p and p.api_key) and not model.startswith("bedrock/"):
        print("Error: No API key configured.", file=sys.stderr)
        sys.exit(1)
    return LiteLLMProvider(
        api_key=p.api_key if p else None,
        api_base=config.get_api_base(),
        default_model=model,
        extra_headers=p.extra_headers if p else None,
        provider_name=config.get_provider_name(),
    )

async def main():
    """
    Runs a single prompt through the AgentLoop and prints the response.
    This bypasses the CLI for testing purposes.
    """
    if len(sys.argv) < 2:
        print("Usage: python run_test.py \"<prompt>\"", file=sys.stderr)
        sys.exit(1)

    prompt = sys.argv[1]

    try:
        config = load_config()
        bus = MessageBus()
        provider = _make_provider(config)

        # Manually define the routing config to ensure the test environment is correct
        llm_routing_config = {
            "powerful_model": "gemini-1.5-pro",
            "fast_model": "gemini-1.5-flash",
            "local_model": "ollama/llama3.1:8b"
        }

        agent_loop = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=config.workspace_path,
            model=config.agents.defaults.model,
            temperature=config.agents.defaults.temperature,
            max_tokens=config.agents.defaults.max_tokens,
            max_iterations=config.agents.defaults.max_tool_iterations,
            memory_window=config.agents.defaults.memory_window,
            brave_api_key=config.tools.web.search.api_key or None,
            exec_config=config.tools.exec,
            restrict_to_workspace=config.tools.restrict_to_workspace,
            llm_routing_config=llm_routing_config,
        )

        response = await agent_loop.process_direct(prompt, session_key="cli-test:direct")
        if response:
            print(response)

    except Exception as e:
        logger.error(f"An error occurred during test execution: {e}")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
