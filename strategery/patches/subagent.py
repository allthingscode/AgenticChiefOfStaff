import sys
from . import BasePatch

class SubagentPatch(BasePatch):
    """Handles specialist routing, subagent model forcing, and tool proxies (Google Hammer)."""
    
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
            print(f"[Launcher] Subagent patch error: {e}")
            return False

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
                print(f"[Strategic] SubagentManager initialized (Model: {current_model})")
                
                # Store MCP server config for subagents
                mcp_data = config_data.get("tools", {}).get("mcpServers", {})
                self._mcp_configs = {k: MCPServerConfig.model_validate(v) for k, v in mcp_data.items()}
                
                self._orig_subagent_init_strategic(*args, **kwargs)
            SubagentManager.__init__ = _patched_subagent_init

        if not hasattr(SubagentManager, "_orig_run_subagent_strategic"):
            SubagentManager._orig_run_subagent_strategic = SubagentManager._run_subagent
            async def _patched_run_subagent(self, task_id, task, label, origin):
                specialists = config_data.get("agents", {}).get("specialists", {})
                selected_model = None
                task_lower = ((label or "") + " " + task).lower()
                for name, spec in specialists.items():
                    if any(kw.lower() in task_lower for kw in spec.get("keywords", [])):
                        selected_model = spec.get("model"); break
                
                if not selected_model:
                    if any(kw in task_lower for kw in ["research", "find", "search"]): selected_model = specialists.get("researcher", {}).get("model")
                    elif any(kw in task_lower for kw in ["architect", "design", "structure"]): selected_model = specialists.get("architect", {}).get("model")
                
                orig_model = self.model
                if selected_model: 
                    self.model = selected_model
                    print(f"[Strategic] Specialist Router: Assigned {selected_model} for task '{label}'")
                
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
        from nanobot.agent.tools.registry import ToolRegistry
        if not hasattr(ToolRegistry, "_orig_tool_execute_strategic"):
            ToolRegistry._orig_tool_execute_strategic = ToolRegistry.execute
            async def _patched_tool_execute(self, name, args):
                if "google-surgical" in str(name) and isinstance(args, dict):
                    if "user_google_email" in args: args["user_google_email"] = user_email
                    if "email" in args: args["email"] = user_email
                    print(f"[Launcher] Google Hammer: {user_email}")
                
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
                    print(f"[Launcher] Heartbeat forced to model: {config_model}")
                self._orig_hb_init_strategic(*args, **kwargs)
            HeartbeatService.__init__ = _patched_hb_init
