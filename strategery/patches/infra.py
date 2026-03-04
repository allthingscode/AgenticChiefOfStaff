import sys
import os
import io
import asyncio
from functools import wraps
from .base import BasePatch
from .lifecycle import lifecycle_manager
from strategery.strategic_logger import strategic_logger

class InfraPatch(BasePatch):
    """Handles Windows-specific infrastructure fixes, lifecycle orchestration, and UTF-8 enforcement."""

    @property
    def name(self) -> str:
        return "Infrastructure (Windows/UTF-8)"

    def apply(self, config: dict) -> bool:
        # 1. Force UTF-8 encoding for Windows stdout/stderr
        if sys.platform == 'win32':
            if getattr(sys.stdout, 'encoding', '').lower() != 'utf-8':
                try:
                    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
                    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
                    strategic_logger.debug("Enforced UTF-8 for Windows stdout/stderr")
                except (AttributeError, io.UnsupportedOperation):
                    pass

            os.environ["PYTHONIOENCODING"] = "utf-8"
            os.environ["PYTHONUTF8"] = "1"

        # 2. Fix the Windows 'Event loop is closed' error and set policy
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            strategic_logger.debug("Set WindowsProactorEventLoopPolicy")

            from asyncio.proactor_events import _ProactorBasePipeTransport

            if not hasattr(_ProactorBasePipeTransport, "_orig_del_strategic"):
                _ProactorBasePipeTransport._orig_del_strategic = _ProactorBasePipeTransport.__del__

                @wraps(_ProactorBasePipeTransport._orig_del_strategic)
                def _patched_del(self):
                    try:
                        self._orig_del_strategic()
                    except (RuntimeError, ValueError) as e:
                        _msg = str(e)
                        if 'Event loop is closed' in _msg or 'I/O operation on closed pipe' in _msg:
                            # Suppress noise during shutdown
                            pass
                        else:
                            raise
                _ProactorBasePipeTransport.__del__ = _patched_del
                strategic_logger.debug("Patched _ProactorBasePipeTransport to suppress closed-loop noise")

        # 3. Setup Global Signal/Lifecycle Handlers
        # We attempt this immediately; the manager handles if no loop is running yet.
        lifecycle_manager.setup_signal_handlers()

        return True

class StrategicMcpManager:
    """
    Manages persistent MCP server connections across subagent spawns.
    Reduces startup overhead and improves responsiveness.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StrategicMcpManager, cls).__new__(cls)
            cls._instance._connections = {} # name -> (session, stack, tools_def)
            cls._instance._lock = asyncio.Lock()
        return cls._instance

    async def get_tools_for_subagent(self, mcp_configs, registry, subagent_id):
        """
        Connects to (or reuses) MCP servers and registers tools in the subagent's registry.
        """
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from contextlib import AsyncExitStack
        from nanobot.agent.tools.mcp import MCPToolWrapper

        async with self._lock:
            for name, cfg in mcp_configs.items():
                try:
                    if name not in self._connections:
                        strategic_logger.info(f"[StrategicMCP] Initializing persistent connection for '{name}'...")
                        stack = AsyncExitStack()
                        
                        if cfg.command:
                            params = StdioServerParameters(
                                command=cfg.command, args=cfg.args, env=cfg.env or None
                            )
                            read, write = await stack.enter_async_context(stdio_client(params))
                        else:
                            strategic_logger.warning(f"[StrategicMCP] Server '{name}' has no command, skipping.")
                            continue

                        session = await stack.enter_async_context(ClientSession(read, write))
                        await session.initialize()
                        
                        tools_response = await session.list_tools()
                        self._connections[name] = (session, stack, tools_response.tools)
                        
                        # Register cleanup
                        lifecycle_manager.register_shutdown_hook(stack.aclose())
                    else:
                        strategic_logger.debug(f"[StrategicMCP] Reusing existing connection for '{name}' for Subagent [{subagent_id}].")

                    session, _, tools_def = self._connections[name]
                    for tool_def in tools_def:
                        wrapper = MCPToolWrapper(session, name, tool_def, tool_timeout=cfg.tool_timeout)
                        registry.register(wrapper)
                        
                except Exception as e:
                    strategic_logger.error(f"[StrategicMCP] Failed to connect to '{name}': {e}")

strategic_mcp_manager = StrategicMcpManager()

