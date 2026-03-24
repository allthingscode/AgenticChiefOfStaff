import os
import sys
import io
import asyncio
from pathlib import Path
from typing import Any, List, Dict, Optional, Tuple
from strategery.strategic_logger import strategic_logger

def resolve_strategic_media_path(context_storage_root: Optional[Path], channel_name: Optional[str] = None) -> Path:
    """Resolves the absolute path for strategic media storage on the D: drive."""
    storage_root = context_storage_root or Path("D:/Nanobot_Storage")
    path = storage_root / "workspace" / "media"
    if channel_name:
        path = path / channel_name
    
    path.mkdir(parents=True, exist_ok=True)
    return path

def list_directory_robust(path_str: str, workspace_path: Path, allowed_dir: Optional[Path] = None) -> str:
    """Robustly lists directory contents, skipping restricted Windows items (BUG-179)."""
    try:
        # We need a helper for path resolution if we want to be truly pure, 
        # but for now, we'll assume the patch provides a resolved path or we use local logic.
        from nanobot.agent.tools.filesystem import _resolve_path
        dir_path = _resolve_path(path_str, workspace_path, allowed_dir)
        
        if not dir_path.exists():
            return f"Error: Directory not found: {path_str}"
        if not dir_path.is_dir():
            return f"Error: Not a directory: {path_str}"

        items = []
        try:
            for item in sorted(dir_path.iterdir()):
                try:
                    prefix = "📁 " if item.is_dir() else "📄 "
                    items.append(f"{prefix}{item.name}")
                except (PermissionError, OSError):
                    # Skip restricted items (junctions) without failing the entire list
                    continue
        except (PermissionError, OSError) as e:
            return f"Error accessing directory contents: {str(e)}"

        if not items:
            return f"Directory {path_str} is empty (or all items are restricted)"

        return "\n".join(items)
    except Exception as e:
        return f"Error listing directory strategically: {str(e)}"

def read_log_file_robust(path_str: str, workspace_path: Path, allowed_dir: Optional[Path], max_chars: int) -> Optional[str]:
    """Reads a log file using Windows-safe encoding (BUG-133)."""
    if not (path_str.lower().endswith(".log") and sys.platform == "win32"):
        return None
        
    try:
        from nanobot.agent.tools.filesystem import _resolve_path
        file_path = _resolve_path(path_str, workspace_path, allowed_dir)
        
        if not file_path.exists():
            return f"Error: File not found: {path_str}"
        
        size = file_path.stat().st_size
        if size > max_chars * 4:
            return f"Error: File too large ({size:,} bytes)."

        # Strategic encoding bridge (BOM safe + backslashreplace)
        with open(file_path, "r", encoding="utf-8-sig", errors="backslashreplace") as f:
            content = f.read()
        
        if len(content) > max_chars:
            return content[:max_chars] + f"\n\n... (truncated)"
        return content
    except Exception as e:
        return f"Error reading log file strategically: {str(e)}"

class McpConnectionManager:
    """Pure logic for managing persistent MCP server connections."""
    def __init__(self):
        self._connections = {}
        self._lock = asyncio.Lock()

    def register_connection(self, name: str, session: Any, stack: Any, tools_def: List[Any]):
        if name not in self._connections:
            strategic_logger.debug(f"[StrategicMCP] Bridged external connection for '{name}'.")
            self._connections[name] = (session, stack, tools_def)

    async def ensure_connection(self, name: str, cfg: Any, shutdown_registrar: Any) -> Optional[Tuple[Any, Any, List[Any]]]:
        """Initializes or retrieves a persistent MCP connection."""
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
                
                # Register for cleanup
                shutdown_registrar(stack.aclose)
                
                return conn
            except Exception as e:
                strategic_logger.error(f"[StrategicMCP] Failed to connect to '{name}': {e}")
                return None

    async def register_tools(self, mcp_configs: Dict[str, Any], registry: Any, shutdown_registrar: Any):
        """Prepares and registers MCP tools for a subagent."""
        from nanobot.agent.tools.mcp import MCPToolWrapper
        
        # Parallel initialization of connections
        tasks = [self.ensure_connection(name, cfg, shutdown_registrar) for name, cfg in mcp_configs.items()]
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

# Global singleton instance for the logic manager
strategic_mcp_logic = McpConnectionManager()
