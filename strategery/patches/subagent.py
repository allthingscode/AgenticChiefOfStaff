import sys
import os
import importlib.util
from pathlib import Path
from . import BasePatch
from strategery.strategic_logger import strategic_logger

def strategic_select_specialist_model(task, label, specialists_config):
    """
    Determines if a task requires a specialist model based on keywords and context.
    """
    task_lower = ((label or "") + " " + task).lower()
    
    for name, spec in specialists_config.items():
        if any(kw.lower() in task_lower for kw in spec.get("keywords", [])):
            return spec.get("model")
            
    if any(kw in task_lower for kw in ["research", "find", "search", "analyze", "report", "audit", "verify", "stale", "email"]): 
        return specialists_config.get("researcher", {}).get("model")
    elif any(kw in task_lower for kw in ["architect", "design", "structure", "plan", "refactor", "implement", "deploy"]): 
        return specialists_config.get("architect", {}).get("model")
        
    return None

class SubagentPatch(BasePatch):
    """
    Enforces a Specialist Economy:
    - High-power tools are BLOCKED from the Main Agent.
    - Subagents are granted Surgical Tools and assigned specialist models.
    """
    
    @property
    def name(self) -> str:
        return "Subagent & Tool Orchestration"

    def apply(self, config_data: dict) -> bool:
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
        from nanobot.agent.tools.base import Tool
        tools_dir = Path(__file__).parent.parent / "tools"
        if not tools_dir.exists(): return

        for file in tools_dir.glob("*.py"):
            if file.name == "__init__.py": continue
            try:
                module_name = f"strategery.tools.{file.stem}"
                spec = importlib.util.spec_from_file_location(module_name, file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and issubclass(attr, Tool) and attr is not Tool):
                            # We use _orig_register if available to bypass our own block
                            reg_func = getattr(registry, "_orig_register_strategic", registry.register)
                            reg_func(attr())
            except Exception as e:
                strategic_logger.error(f"Error loading strategic tool {file.name}: {e}")

    def _patch_subagent_manager(self, config_data):
        from nanobot.agent.subagent import SubagentManager
        from nanobot.agent.tools.registry import ToolRegistry

        if not hasattr(SubagentManager, "_orig_run_subagent_strategic"):
            SubagentManager._orig_run_subagent_strategic = SubagentManager._run_subagent
            patch_self = self

            async def _patched_run_subagent(self, task_id, task, label, origin):
                specialists = config_data.get("agents", {}).get("specialists", {})
                selected_model = strategic_select_specialist_model(task, label, specialists)
                
                final_model = selected_model if selected_model else self.model
                strategic_logger.info(f"Subagent Spawned: [{task_id}] '{label}' using model '{final_model}'")
                
                orig_registry_cls = ToolRegistry
                class StrategicSubagentRegistry(ToolRegistry):
                    def __init__(self, *args, **kwargs):
                        # Tag it BEFORE super().__init__ so internal registrations are allowed
                        self._is_strategic_specialist = True
                        super().__init__(*args, **kwargs)
                        patch_self._load_strategic_tools(self)

                import nanobot.agent.subagent
                nanobot.agent.subagent.ToolRegistry = StrategicSubagentRegistry
                
                orig_model = self.model
                self.model = final_model
                
                try:
                    await self._orig_run_subagent_strategic(task_id, task, label, origin)
                    strategic_logger.info(f"Subagent Execution Finished: [{task_id}] '{label}'")
                    return None
                finally:
                    self.model = orig_model
                    nanobot.agent.subagent.ToolRegistry = orig_registry_cls

            SubagentManager._run_subagent = _patched_run_subagent

        if not hasattr(SubagentManager, "_orig_announce_result_strategic"):
            SubagentManager._orig_announce_result_strategic = SubagentManager._announce_result
            
            async def _patched_announce_result(self, task_id, label, task, result, origin, status):
                from nanobot.bus.events import InboundMessage
                status_text = "completed successfully" if status == "ok" else "failed"

                announce_content = f"""### 🛡️ SPECIALIST SUBAGENT REPORT (FINAL)
[Subagent '{label}' {status_text}]

**Original Task:** {task}

**Result Data:**
{result}

---
### ⚖️ ORCHESTRATOR DIRECTIVE (CRITICAL)
1. **Do NOT Attempt to Verify:** You are strictly forbidden from calling any tools (Google, AI Search, etc.) to "verify" this result. The specialist has already performed the work.
2. **Synthesize Only:** Your ONLY remaining responsibility is to present this data to the user in a natural, helpful summary.
3. **Task Conclusion:** This specific task is now CLOSED.
"""
                msg = InboundMessage(
                    channel="system",
                    sender_id="subagent",
                    chat_id=f"{origin['channel']}:{origin['chat_id']}",
                    content=announce_content,
                )
                await self.bus.publish_inbound(msg)
                strategic_logger.debug(f"Subagent [{task_id}] announced result with Strategic Orchestrator Directives.")

            SubagentManager._announce_result = _patched_announce_result

        if not hasattr(SubagentManager, "_orig_build_prompt_strategic"):
            SubagentManager._orig_build_prompt_strategic = SubagentManager._build_subagent_prompt
            def _patched_build_prompt(self):
                is_pro = "pro" in str(self.model).lower()
                role_msg = "\n## SPECIALIST ROLE: High-Depth Research & Architecture\nYou have been assigned a PRO model because this task requires precision. Exhaustively verify facts." if is_pro else ""
                
                reset_instr = f"""
{role_msg}
## CRITICAL OVERRIDE & DESIGN MANDATES
1. **Tool Naming:** You MUST use the exact, full name for all tools (e.g. mcp_google-surgical_search_emails).
2. **Exclusive Access:** You have EXCLUSIVE access to mcp_google-surgical_, mcp_google-ai-search_, and mcp_email-reporter_. The main agent CANNOT use these.
3. **Verify Memory:** Always verify 'Retrieved Historical Context' against fresh research to prevent stale data.
"""
                return self._orig_build_prompt_strategic() + reset_instr
            SubagentManager._build_subagent_prompt = _patched_build_prompt

    def _patch_tool_registry(self, user_email):
        from nanobot.agent.tools.registry import ToolRegistry

        if not hasattr(ToolRegistry, "_orig_register_strategic"):
            ToolRegistry._orig_register_strategic = ToolRegistry.register

            def _patched_register(registry_self, tool):
                name = getattr(tool, "name", str(tool))
                is_high_power = any(hp in name for hp in ["google-surgical", "google-ai-search", "email-reporter", "strategic_"])

                # Main agent registry (no specialist tag)
                if is_high_power and not getattr(registry_self, "_is_strategic_specialist", False):
                    strategic_logger.debug(f"Tool Stripping: Blocked registration of '{name}' for Main Agent (forced delegation).")
                    return

                return registry_self._orig_register_strategic(tool)

            ToolRegistry.register = _patched_register

        if not hasattr(ToolRegistry, "_orig_tool_execute_strategic"):
            ToolRegistry._orig_tool_execute_strategic = ToolRegistry.execute
            async def _patched_tool_execute(self, name, args):
                is_high_power = any(hp in str(name) for hp in ["google-surgical", "google-ai-search", "email-reporter", "strategic_"])

                # Hard Block & Circuit Breaker: Prevent Main Agent from looping on blocked tools
                if is_high_power and not getattr(self, "_is_strategic_specialist", False):
                    attempts = getattr(self, "_strategic_block_attempts", 0) + 1
                    self._strategic_block_attempts = attempts
                    
                    strategic_logger.warning(f"SECURITY ALERT: Main Agent attempted to execute high-power tool '{name}' (Attempt {attempts}). Execution blocked.")
                    
                    if attempts >= 2:
                        return f"CRITICAL ERROR: Access Denied. Your internal registry is HARD-LOCKED for tool '{name}'. Repeated attempts are a violation of your Strategic Mandates. You MUST STOP trying to call this tool directly and instead spawn a specialist subagent immediately or explain the failure to the user."
                    
                    return f"ERROR: The tool '{name}' is restricted to SPECIALIST subagents. You MUST use the 'spawn' tool to delegate this task to a researcher or architect."

                if "google-surgical" in str(name) and isinstance(args, dict):
                    if "user_google_email" in args: args["user_google_email"] = user_email
                    if "email" in args: args["email"] = user_email

                if name == "web_search":
                    return "ERROR: The 'web_search' tool is DEPRECATED. You MUST use 'mcp_google-ai-search_search_ai' via a subagent."

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
                    else: kwargs["model"] = config_model
                self._orig_hb_init_strategic(*args, **kwargs)
            HeartbeatService.__init__ = _patched_hb_init
