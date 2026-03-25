import sys
import os
import io
import asyncio
from typing import Any, List
from functools import wraps
from .base import BasePatch, PatchResult, PatchContext
from .lifecycle import lifecycle_manager
from strategery.strategic_logger import strategic_logger

def strategic_bridge_mcp_sessions(mcp_configs, registry, stack, core_connect_func):
    """
    Wraps core MCP connection logic to register sessions with our Strategic manager.
    Extracted to module level for testing.
    """
    async def _bridged_connect(configs, reg, st):
        from strategery.logic.infra_logic import strategic_mcp_logic
        # 1. Call original core connection logic
        results = await core_connect_func(configs, reg, st)
        
        # 2. Bridging: Since core doesn't return the (session, stack, tools) directly,
        # we scan the registry for the newly created MCP tools.
        for name in configs.keys():
            if name not in strategic_mcp_logic._connections:
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

                            strategic_mcp_logic.register_connection(name, session, st, server_tools_defs)
                            break
        return results
    return _bridged_connect

class InfraPatch(BasePatch):
    """Handles Windows-specific infrastructure fixes, lifecycle orchestration, and UTF-8 enforcement."""

    @property
    def name(self) -> str:
        return "Infrastructure (Windows/UTF-8)"

    @property
    def required_symbols(self) -> List[str]:
        return [
            "asyncio.WindowsProactorEventLoopPolicy",
            "nanobot.agent.tools.mcp.connect_mcp_servers",
            "nanobot.agent.tools.filesystem.ReadFileTool.execute"
        ]

    def apply(self, context: PatchContext) -> PatchResult:
        result = PatchResult(patch_name=self.name, success=True)
        try:
            if sys.platform == 'win32':
                if getattr(sys.stdout, 'encoding', '').lower() != 'utf-8':
                    try:
                        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
                        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
                        strategic_logger.debug("Enforced UTF-8 for Windows stdout/stderr")
                        result.affected_symbols.extend(["sys.stdout", "sys.stderr"])
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
                                    result.affected_symbols.append(f"logging.handler.{handler.__class__.__name__}")
                                except (AttributeError, io.UnsupportedOperation):
                                    pass
                    strategic_logger.debug("Hardened standard logging handlers with 'backslashreplace'")
                except Exception as e:
                    strategic_logger.error(f"Failed to harden unicode logging: {e}")

            if sys.platform == 'win32':
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                strategic_logger.debug("Set WindowsProactorEventLoopPolicy")
                result.affected_symbols.append("asyncio.WindowsProactorEventLoopPolicy")

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
                    result.affected_symbols.append("_ProactorBasePipeTransport.__del__")

            lifecycle_manager.setup_signal_handlers()
            self._patch_mcp_bridging()
            result.affected_symbols.append("nanobot.agent.tools.mcp.connect_mcp_servers")
            
            self._patch_filesystem_tools()
            result.affected_symbols.append("nanobot.agent.tools.filesystem.ReadFileTool.execute")
            
            self._patch_listdir_tool()
            result.affected_symbols.append("nanobot.agent.tools.filesystem.ListDirTool.execute")
            
            self._patch_media_redirection(context)
            result.affected_symbols.append("nanobot.config.paths.get_media_dir")
            
            return result
        except Exception as e:
            import traceback
            result.success = False
            result.error_msg = str(e)
            result.traceback = traceback.format_exc()
            strategic_logger.error(f"Infrastructure patch error: {e}")
            return result

    def _patch_media_redirection(self, context: PatchContext):
        """Globally redirects all media downloads to the D: drive (BUG-201, BUG-203)."""
        import nanobot.config.paths as core_paths
        from pathlib import Path
        import sys
        from strategery.logic.infra_logic import resolve_strategic_media_path
        
        # Logic Isolation (BUG-212): Use pure logic for path resolution
        strategic_media_root = resolve_strategic_media_path(context.storage_root)
        
        def _strategic_get_media_dir(channel_name: str | None = None) -> Path:
            return resolve_strategic_media_path(context.storage_root, channel_name)

        # 1. Patch the source
        if not hasattr(core_paths, "get_media_dir_strategic"):
            core_paths.get_media_dir_strategic = core_paths.get_media_dir
            core_paths.get_media_dir = _strategic_get_media_dir
            strategic_logger.info(f"Globally redirected media to: {strategic_media_root}")

        # 2. Patch already-imported references in channels (Ironclad Mandate)
        channels = ["telegram", "discord", "feishu", "matrix"]
        for channel in channels:
            module_name = f"nanobot.channels.{channel}"
            if module_name in sys.modules:
                mod = sys.modules[module_name]
                if hasattr(mod, "get_media_dir"):
                    mod.get_media_dir = _strategic_get_media_dir
                    strategic_logger.debug(f"Ironclad: Redirected get_media_dir in {module_name}")

    def _patch_listdir_tool(self):
        """Patches ListDirTool to handle Windows-specific junction points and restricted items (BUG-179)."""
        from nanobot.agent.tools.filesystem import ListDirTool
        from strategery.logic.infra_logic import list_directory_robust
        
        if not hasattr(ListDirTool, "_orig_execute_strategic"):
            ListDirTool._orig_execute_strategic = ListDirTool.execute
            
            async def _patched_execute(self, path: str, **kwargs: Any) -> str:
                # Logic Isolation (BUG-212): Robust listing moved to logic
                return list_directory_robust(path, self._workspace, self._allowed_dir)

            ListDirTool.execute = _patched_execute
            strategic_logger.debug("Patched ListDirTool for robust Windows directory listing (BUG-179).")

    def _patch_filesystem_tools(self):
        """Patches ReadFileTool to handle Windows-specific log encoding (BUG-133)."""
        from nanobot.agent.tools.filesystem import ReadFileTool
        from strategery.logic.infra_logic import read_log_file_robust
        
        if not hasattr(ReadFileTool, "_orig_execute_strategic"):
            ReadFileTool._orig_execute_strategic = ReadFileTool.execute
            
            async def _patched_execute(self, path: str, **kwargs: Any) -> str:
                # Logic Isolation (BUG-212): Log reading logic moved to logic
                res = read_log_file_robust(path, self._workspace, self._allowed_dir, self._MAX_CHARS)
                if res is not None:
                    return res
                
                return await self._orig_execute_strategic(path, **kwargs)

            ReadFileTool.execute = _patched_execute
            strategic_logger.debug("Patched ReadFileTool for strategic log handling (BUG-133).")

    def _patch_mcp_bridging(self):
        import nanobot.agent.tools.mcp as core_mcp
        if not hasattr(core_mcp, "connect_mcp_servers_strategic"):
            core_mcp.connect_mcp_servers_strategic = core_mcp.connect_mcp_servers
            # Logic Isolation (BUG-212): Bridge logic moved to logic manager
            core_mcp.connect_mcp_servers = strategic_bridge_mcp_sessions(
                None, None, None, core_mcp.connect_mcp_servers_strategic
            )
            strategic_logger.debug("Bridged core MCP connection logic with Strategic Manager.")

# Logic Isolation (BUG-212): StrategicMcpManager moved to strategery.logic.infra_logic
