import sys
import os
import io
import asyncio
from functools import wraps
from .base import BasePatch
from .lifecycle import lifecycle_manager
from strategery.strategic_logger import strategic_logger

def strategic_bridge_mcp_sessions(mcp_configs, registry, stack, core_connect_func):
    """
    Wraps core MCP connection logic to register sessions with our Strategic manager.
    Extracted to module level for testing.
    """
    async def _bridged_connect(configs, reg, st):
        # 1. Call original core connection logic
        results = await core_connect_func(configs, reg, st)
        
        # 2. Bridging: Since core doesn't return the (session, stack, tools) directly,
        # we scan the registry for the newly created MCP tools.
        for name in configs.keys():
            if name not in strategic_mcp_manager._connections:
                for tool_inst in reg._tools.values():
                    if hasattr(tool_inst, "name") and tool_inst.name.startswith(f"mcp_{name}_"):
                        session = getattr(tool_inst, "_session", None)
                        if session:
                            from dataclasses import make_dataclass
                            ToolDef = make_dataclass("ToolDef", [("name", str), ("description", str), ("inputSchema", dict)])
                            
                            server_tools_defs = []
                            for t in reg._tools.values():
                                if hasattr(t, "name") and t.name.startswith(f"mcp_{name}_"):
                                    orig_name = getattr(t, "_original_name", t.name.replace(f"mcp_{name}_", ""))
                                    server_tools_defs.append(ToolDef(
                                        name=orig_name,
                                        description=t.description,
                                        inputSchema=t.parameters
                                    ))

                            strategic_mcp_manager.register_connection(name, session, st, server_tools_defs)
                            break
        return results
    return _bridged_connect

class InfraPatch(BasePatch):
    """Handles Windows-specific infrastructure fixes, lifecycle orchestration, and UTF-8 enforcement."""

    @property
    def name(self) -> str:
        return "Infrastructure (Windows/UTF-8)"

    def apply(self, config: dict) -> bool:
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

            # BUG-041/096: Harden standard logging handlers against UnicodeEncodeError, but skip pytest loggers
            try:
                import logging
                root = logging.getLogger()
                for handler in root.handlers:
                    if isinstance(handler, logging.FileHandler) or "Capture" in handler.__class__.__name__:
                        continue

                    if isinstance(handler, logging.StreamHandler):
                        if hasattr(handler.stream, 'encoding') and handler.stream:
                            try:
                                handler.stream = io.TextIOWrapper(
                                    handler.stream.buffer, 
                                    encoding=handler.stream.encoding, 
                                    errors='backslashreplace',
                                    line_buffering=True
                                )
                            except (AttributeError, io.UnsupportedOperation):
                                pass
                strategic_logger.debug("Hardened standard logging handlers with 'backslashreplace'")
            except Exception as e:
                strategic_logger.error(f"Failed to harden unicode logging: {e}")

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
                            pass
                        else:
                            raise
                _ProactorBasePipeTransport.__del__ = _patched_del

        lifecycle_manager.setup_signal_handlers()
        self._patch_mcp_bridging()
        return True

    def _patch_mcp_bridging(self):
        import nanobot.agent.tools.mcp as core_mcp
        if not hasattr(core_mcp, "connect_mcp_servers_strategic"):
            core_mcp.connect_mcp_servers_strategic = core_mcp.connect_mcp_servers
            core_mcp.connect_mcp_servers = strategic_bridge_mcp_sessions(
                None, None, None, core_mcp.connect_mcp_servers_strategic
            )
            strategic_logger.debug("Bridged core MCP connection logic with Strategic Manager.")

class StrategicMcpManager:
    """Manages persistent MCP server connections across subagent spawns."""
    _instance = None
    
    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._connections = {} 
            self._lock = asyncio.Lock()
            self._initialized = True

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StrategicMcpManager, cls).__new__(cls)
        return cls._instance

    def register_connection(self, name, session, stack, tools_def):
        if name not in self._connections:
            strategic_logger.debug(f"[StrategicMCP] Bridged external connection for '{name}'.")
            self._connections[name] = (session, stack, tools_def)

    async def _ensure_connection(self, name, cfg):
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client, StdioServerParameters
        from contextlib import AsyncExitStack

        async with self._lock:
            if name in self._connections:
                return self._connections[name]

            try:
                strategic_logger.info(f"[StrategicMCP] Initializing persistent connection for '{name}'...")
                stack = AsyncExitStack()
                if not cfg.command: return None

                params = StdioServerParameters(command=cfg.command, args=cfg.args, env=cfg.env or None)
                client_ctx = stdio_client(params)
                read, write = await stack.enter_async_context(client_ctx)
                session_ctx = ClientSession(read, write)
                session = await stack.enter_async_context(session_ctx)
                await session.initialize()
                
                tools_response = await session.list_tools()
                conn = (session, stack, tools_response.tools)
                self._connections[name] = conn
                lifecycle_manager.register_shutdown_hook(stack.aclose)
                return conn
            except Exception as e:
                strategic_logger.error(f"[StrategicMCP] Failed to connect to '{name}': {e}")
                return None

    async def get_tools_for_subagent(self, mcp_configs, registry, subagent_id):
        from nanobot.agent.tools.mcp import MCPToolWrapper
        tasks = [self._ensure_connection(name, cfg) for name, cfg in mcp_configs.items()]
        results = await asyncio.gather(*tasks)
        for (name, cfg), conn in zip(mcp_configs.items(), results):
            if not conn: continue
            try:
                session, _, tools_def = conn
                for tool_def in tools_def:
                    wrapper = MCPToolWrapper(session, name, tool_def, tool_timeout=60)
                    registry.register(wrapper)
            except Exception as e:
                strategic_logger.error(f"[StrategicMCP] Failed to register tools for '{name}': {e}")

strategic_mcp_manager = StrategicMcpManager()
