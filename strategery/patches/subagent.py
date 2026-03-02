import sys
import os
import importlib.util
from pathlib import Path
from . import BasePatch
from strategery.strategic_logger import strategic_logger

def strategic_select_specialist_model(task, label, specialists_config):
    # ... (rest of logic)
    task_lower = ((label or "") + " " + task).lower()
    
    # 1. Exact specialist match
    for name, spec in specialists_config.items():
        if any(kw.lower() in task_lower for kw in spec.get("keywords", [])):
            return spec.get("model")
            
    # 2. Broader category match
    if any(kw in task_lower for kw in ["research", "find", "search", "analyze", "report", "audit"]): 
        return specialists_config.get("researcher", {}).get("model")
    elif any(kw in task_lower for kw in ["architect", "design", "structure", "plan", "refactor", "implement"]): 
        return specialists_config.get("architect", {}).get("model")
        
    return None

class SubagentPatch(BasePatch):
    """Handles specialist routing, subagent model forcing, and tool side-loading."""
    
    @property
    def name(self) -> str:
        return "Subagent & Tool Orchestration"

    def apply(self, config_data: dict) -> bool:
        # We need USER_EMAIL for the Google Hammer
        from .config import load_strategic_context
        _, user_email, _ = load_strategic_context()
        
        try:
            self._patch_subagent_manager(config_data)
            self._patch_tool_registry(user_email)
            self._patch_heartbeat(config_data)
            return True
        except Exception as e:
            strategic_logger.error(f"Subagent patch error: {e}")
            return False

    def _load_strategic_tools(self, registry):
        # ... (rest of method)
        from nanobot.agent.tools.base import Tool
        
        tools_dir = Path(__file__).parent.parent / "tools"
        if not tools_dir.exists():
            return

        strategic_logger.debug(f"Scanning for strategic tools in {tools_dir}...")
        
        for file in tools_dir.glob("*.py"):
            if file.name == "__init__.py":
                continue
            
            try:
                module_name = f"strategery.tools.{file.stem}"
                spec = importlib.util.spec_from_file_location(module_name, file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Find Tool subclasses in the module
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            issubclass(attr, Tool) and 
                            attr is not Tool):
                            
                            try:
                                tool_instance = attr()
                                registry.register(tool_instance)
                                strategic_logger.info(f"Side-loaded strategic tool: {tool_instance.name}")
                            except Exception as te:
                                strategic_logger.error(f"Error instantiating tool {attr_name} from {file.name}: {te}")
            except Exception as e:
                strategic_logger.error(f"Error loading strategic tool module {file.name}: {e}")

    def _patch_subagent_manager(self, config_data):
        from nanobot.agent.subagent import SubagentManager
        from nanobot.config.schema import MCPServerConfig

        if not hasattr(SubagentManager, "_orig_subagent_init_strategic"):
            SubagentManager._orig_subagent_init_strategic = SubagentManager.__init__
            def _patched_subagent_init(self, *args, **kwargs):
                config_model = config_data.get("agents", {}).get("subagent", {}).get("model")
                if config_model:
                    if len(args) >= 4:
                        args = list(args)
                        args[3] = config_model
                    else:
                        kwargs["model"] = config_model
                
                current_model = kwargs.get('model') or (args[3] if len(args) > 3 else 'auto')
                strategic_logger.debug(f"SubagentManager initialized (Model: {current_model})")
                
                # Store MCP server config for subagents
                mcp_data = config_data.get("tools", {}).get("mcpServers", {})
                self._mcp_configs = {k: MCPServerConfig.model_validate(v) for k, v in mcp_data.items()}
                
                self._orig_subagent_init_strategic(*args, **kwargs)
            SubagentManager.__init__ = _patched_subagent_init

        if not hasattr(SubagentManager, "_orig_run_subagent_strategic"):
            SubagentManager._orig_run_subagent_strategic = SubagentManager._run_subagent
            async def _patched_run_subagent(self, task_id, task, label, origin):
                specialists = config_data.get("agents", {}).get("specialists", {})
                selected_model = strategic_select_specialist_model(task, label, specialists)
                
                orig_model = self.model
                if selected_model: 
                    self.model = selected_model
                    strategic_logger.info(f"Specialist Router: Assigned {selected_model} for task '{label}'")
                
                try:
                    return await self._orig_run_subagent_strategic(task_id, task, label, origin)
                finally:
                    self.model = orig_model
            SubagentManager._run_subagent = _patched_run_subagent

        if not hasattr(SubagentManager, "_orig_build_prompt_strategic"):
            SubagentManager._orig_build_prompt_strategic = SubagentManager._build_subagent_prompt
            def _patched_build_prompt(self):
                reset_instr = """

## CRITICAL OVERRIDE & DESIGN MANDATES
1. **Tool Naming:** You MUST use the exact, full name for all tools as provided in your tool list. For MCP tools, this ALWAYS includes the `mcp_` prefix (e.g., `mcp_email-reporter_send_email_report`). Do NOT abbreviate or strip the namespace.
2. **Tool Deprecation:** The standard `mcp_google-workspace_` tools are DEPRECATED. They are unstable and do not target the correct mailbox. DO NOT use them.
3. **Surgical Tools:** Use ONLY `mcp_google-surgical_` tools for Tasks and Calendar. Use `mcp_email-reporter_` for all outbound briefings. These custom wrappers provide precision and use the correct user credentials.
4. **Prioritize Advanced Search:** Always prioritize `mcp_google-ai-search` over the base `web_search`.
5. **Specialist Selection:** If you have been assigned to this task with `gemini-1.5-pro` (check the logs if available), it is because this task requires high-depth reasoning (Research, Architecture, or Planning). Focus on thoroughness.
"""
                return self._orig_build_prompt_strategic() + reset_instr
            SubagentManager._build_subagent_prompt = _patched_build_prompt

    def _patch_tool_registry(self, user_email):
        # ... (rest of method)
        from nanobot.agent.tools.registry import ToolRegistry
        
        # 1. Patch __init__ to side-load tools
        if not hasattr(ToolRegistry, "_orig_init_strategic"):
            ToolRegistry._orig_init_strategic = ToolRegistry.__init__
            
            # We need to capture 'self' (the SubagentPatch instance) to call _load_strategic_tools
            patch_self = self
            
            def _patched_init(registry_self, *args, **kwargs):
                registry_self._orig_init_strategic(*args, **kwargs)
                patch_self._load_strategic_tools(registry_self)
            
            ToolRegistry.__init__ = _patched_init

        # 2. Patch execute for Google Hammer and Deprecations
        if not hasattr(ToolRegistry, "_orig_tool_execute_strategic"):
            ToolRegistry._orig_tool_execute_strategic = ToolRegistry.execute
            async def _patched_tool_execute(self, name, args):
                if "google-surgical" in str(name) and isinstance(args, dict):
                    if "user_google_email" in args: args["user_google_email"] = user_email
                    if "email" in args: args["email"] = user_email
                    strategic_logger.debug(f"Google Hammer applied for: {user_email}")
                
                if name == "exec" and sys.platform == "win32" and isinstance(args, dict):
                    cmd = args.get("command", "").strip().lower()
                    if cmd == "date": args["command"] = "date /t"
                    elif cmd == "time": args["command"] = "time /t"
                
                if name == "web_search":
                    return "ERROR: The 'web_search' tool is DEPRECATED and disabled. You MUST use 'mcp_google-ai-search_search_ai' instead."

                return await self._orig_tool_execute_strategic(name, args)
            ToolRegistry.execute = _patched_tool_execute

    def _patch_heartbeat(self, config_data):
        from nanobot.heartbeat.service import HeartbeatService
        if not hasattr(HeartbeatService, "_orig_hb_init_strategic"):
            HeartbeatService._orig_hb_init_strategic = HeartbeatService.__init__
            def _patched_hb_init(self, *args, **kwargs):
                config_model = config_data.get("agents", {}).get("heartbeat", {}).get("model")
                if config_model:
                    if len(args) >= 2:
                        args = list(args)
                        args[1] = config_model
                    else:
                        kwargs["model"] = config_model
                    strategic_logger.info(f"Heartbeat forced to model: {config_model}")
                self._orig_hb_init_strategic(*args, **kwargs)
            HeartbeatService.__init__ = _patched_hb_init
