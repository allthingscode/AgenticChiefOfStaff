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

    async def _ensure_connection(self, name, cfg):
        """Internal helper to ensure a single MCP server is connected."""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from contextlib import AsyncExitStack

        async with self._lock:
            if name in self._connections:
                return self._connections[name]

            try:
                strategic_logger.info(f"[StrategicMCP] Initializing persistent connection for '{name}'...")
                stack = AsyncExitStack()
                
                if not cfg.command:
                    strategic_logger.warning(f"[StrategicMCP] Server '{name}' has no command, skipping.")
                    return None

                params = StdioServerParameters(
                    command=cfg.command, args=cfg.args, env=cfg.env or None
                )
                read, write = await stack.enter_async_context(stdio_client(params))
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                
                tools_response = await session.list_tools()
                conn = (session, stack, tools_response.tools)
                self._connections[name] = conn
                
                # Register cleanup
                lifecycle_manager.register_shutdown_hook(stack.aclose)
                return conn
            except Exception as e:
                strategic_logger.error(f"[StrategicMCP] Failed to connect to '{name}': {e}")
                return None

    async def get_tools_for_subagent(self, mcp_configs, registry, subagent_id):
        """
        Connects to (or reuses) MCP servers in parallel and registers tools in the subagent's registry.
        """
        from nanobot.agent.tools.mcp import MCPToolWrapper

        # 1. Parallelize connection attempts
        tasks = [self._ensure_connection(name, cfg) for name, cfg in mcp_configs.items()]
        results = await asyncio.gather(*tasks)

        # 2. Register tools sequentially (fast)
        for (name, cfg), conn in zip(mcp_configs.items(), results):
            if not conn:
                continue

            try:
                session, _, tools_def = conn
                strategic_logger.debug(f"[StrategicMCP] Registering tools from '{name}' for Subagent [{subagent_id}].")
                for tool_def in tools_def:
                    wrapper = MCPToolWrapper(session, name, tool_def, tool_timeout=cfg.tool_timeout)
                    registry.register(wrapper)
            except Exception as e:
                strategic_logger.error(f"[StrategicMCP] Failed to register tools for '{name}': {e}")

strategic_mcp_manager = StrategicMcpManager()

