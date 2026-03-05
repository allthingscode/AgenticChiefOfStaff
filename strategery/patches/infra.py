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

        # 4. Bridge Core MCP sessions with Strategic Manager (BUG-054)
        self._patch_mcp_bridging()

        return True

    def _patch_mcp_bridging(self):
        """Wraps core MCP connection logic to register sessions with our Strategic manager."""
        import nanobot.agent.tools.mcp as core_mcp
        
        if not hasattr(core_mcp, "connect_mcp_servers_strategic"):
            core_mcp.connect_mcp_servers_strategic = core_mcp.connect_mcp_servers
            
            async def _bridged_connect(mcp_configs, registry, stack):
                # 1. Capture the initial state of the Strategic manager connections
                existing_before = set(strategic_mcp_manager._connections.keys())
                
                # 2. Call original core connection logic (which populates the registry)
                # Note: core_mcp.connect_mcp_servers_strategic is the original 3-arg function.
                results = await core_mcp.connect_mcp_servers_strategic(mcp_configs, registry, stack)
                
                # 3. Bridging: Since core doesn't return the (session, stack, tools) directly,
                # we must reach into the registry to extract the sessions we just created
                # for our Strategic singleton.
                for name in mcp_configs.keys():
                    if name not in strategic_mcp_manager._connections:
                        # Scan the registry for the newly created MCP tools
                        for tool_inst in registry._tools.values():
                            # We check if the tool belongs to this server and has a session
                            if hasattr(tool_inst, "name") and tool_inst.name.startswith(f"mcp_{name}_"):
                                # Use getattr to be safe with private attributes
                                session = getattr(tool_inst, "_session", None)
                                if session:
                                    # Capture the tool definition to recreate it for subagents
                                    # We need a mock tool_def object that has a .name attribute
                                    from dataclasses import make_dataclass
                                    ToolDef = make_dataclass("ToolDef", [("name", str), ("description", str), ("inputSchema", dict)])
                                    
                                    # We need to collect ALL tools for this server
                                    server_tools_defs = []
                                    for t in registry._tools.values():
                                        if hasattr(t, "name") and t.name.startswith(f"mcp_{name}_"):
                                            # Reconstruct the original MCP tool_def structure
                                            # We strip the 'mcp_{name}_' prefix to get the original name
                                            orig_name = getattr(t, "_original_name", t.name.replace(f"mcp_{name}_", ""))
                                            server_tools_defs.append(ToolDef(
                                                name=orig_name,
                                                description=t.description,
                                                inputSchema=t.parameters
                                            ))

                                    # Register the session and the full list of tool definitions
                                    strategic_mcp_manager.register_connection(
                                        name, session, stack, server_tools_defs
                                    )
                                    break
                
                return results
                
            core_mcp.connect_mcp_servers = _bridged_connect
            strategic_logger.debug("Bridged core MCP connection logic with Strategic Manager.")

class StrategicMcpManager:
    """
    Manages persistent MCP server connections across subagent spawns.
    Reduces startup overhead and improves responsiveness.
    """
    _instance = None
    
    def __init__(self):
        # Already initialized in __new__?
        if not hasattr(self, "_initialized"):
            self._connections = {} # name -> (session, stack, tools_def)
            self._lock = asyncio.Lock()
            self._initialized = True

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StrategicMcpManager, cls).__new__(cls)
        return cls._instance

    def register_connection(self, name, session, stack, tools_def):
        """Allows external logic (like the core patch) to register existing MCP sessions."""
        if name not in self._connections:
            strategic_logger.debug(f"[StrategicMCP] Bridged external connection for '{name}'.")
            self._connections[name] = (session, stack, tools_def)

    async def _ensure_connection(self, name, cfg):
        """Internal helper to ensure a single MCP server is connected."""
        # Use local imports to avoid early-init circular issues
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client, StdioServerParameters
        from contextlib import AsyncExitStack

        # Use an external lock if necessary, but self._lock should work in async
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
                
                # Enter AsyncExitStack and setup stdio client
                client_ctx = stdio_client(params)
                read, write = await stack.enter_async_context(client_ctx)
                
                # Setup session
                session_ctx = ClientSession(read, write)
                session = await stack.enter_async_context(session_ctx)
                await session.initialize()
                
                tools_response = await session.list_tools()
                conn = (session, stack, tools_response.tools)
                self._connections[name] = conn
                
                # Register cleanup with the strategic lifecycle manager
                lifecycle_manager.register_shutdown_hook(stack.aclose)
                return conn
            except Exception as e:
                strategic_logger.error(f"[StrategicMCP] Failed to connect to '{name}': {e}", exc_info=True)
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
                    # Use a generous 60s timeout for specialists (BUG-063)
                    wrapper = MCPToolWrapper(session, name, tool_def, tool_timeout=60)
                    registry.register(wrapper)
            except Exception as e:
                strategic_logger.error(f"[StrategicMCP] Failed to register tools for '{name}': {e}")

strategic_mcp_manager = StrategicMcpManager()

