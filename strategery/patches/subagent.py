import sys
import os
import importlib.util
import re
import asyncio
import json
from pathlib import Path
from .base import BasePatch
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
    - Subagents are granted Surgical Tools (including MCP) and assigned specialist models.
    - Idle Polling Loops are detected and broken.
    - CLI-based tool bypass via 'exec' is detected and blocked.
    """
    
    # patterns to block for main agent (case-insensitive)
    BLOCKED_PATTERNS = [
        "google", 
        "ai-search", 
        "email-reporter", 
        "strategic_", 
        "web_search"
    ]

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
        from nanobot.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
        from nanobot.agent.tools.shell import ExecTool
        from nanobot.agent.tools.web import WebFetchTool, WebSearchTool
        from nanobot.agent.tools.mcp import connect_mcp_servers
        from nanobot.config.schema import Config
        from contextlib import AsyncExitStack

        # Replace the entire _run_subagent to inject MCP and Specialist Logic
        async def _strategic_run_subagent(self, task_id, task, label, origin):
            strategic_logger.info(f"Subagent [{task_id}] starting task: {label}")
            
            # 1. Model Selection
            specialists = config_data.get("agents", {}).get("specialists", {})
            selected_model = strategic_select_specialist_model(task, label, specialists)
            final_model = selected_model if selected_model else self.model
            
            strategic_logger.info(f"Subagent Specialist Assigned: model='{final_model}'")

            try:
                async with AsyncExitStack() as stack:
                    # 2. Build Tool Registry (Specialist Mode)
                    tools = ToolRegistry()
                    tools._is_strategic_specialist = True
                    
                    allowed_dir = self.workspace if self.restrict_to_workspace else None
                    tools.register(ReadFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
                    tools.register(WriteFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
                    tools.register(EditFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
                    tools.register(ListDirTool(workspace=self.workspace, allowed_dir=allowed_dir))
                    tools.register(ExecTool(
                        working_dir=str(self.workspace),
                        timeout=self.exec_config.timeout,
                        restrict_to_workspace=self.restrict_to_workspace,
                        path_append=self.exec_config.path_append,
                    ))
                    tools.register(WebSearchTool(api_key=self.brave_api_key, proxy=self.web_proxy))
                    tools.register(WebFetchTool(proxy=self.web_proxy))
                    
                    # 3. Inject Strategic Tools & MCP
                    # Use Pydantic to validate and convert raw config to objects for connect_mcp_servers
                    try:
                        # Clean config for Pydantic (strip strategic keys)
                        from .config import strategic_migrate_config
                        # We make a deep copy to ensure stripping doesn't affect the shared config_data
                        pydantic_cfg = strategic_migrate_config(json.loads(json.dumps(config_data)))
                        
                        validated_config = Config.model_validate(pydantic_cfg)
                        mcp_configs = validated_config.tools.mcp_servers
                        if mcp_configs:
                            strategic_logger.debug(f"Subagent [{task_id}]: Connecting to {len(mcp_configs)} MCP servers...")
                            # FIXED: Signature order is (configs, tools, stack)
                            await connect_mcp_servers(mcp_configs, tools, stack)
                    except Exception as mcp_err:
                        strategic_logger.error(f"Subagent [{task_id}] MCP setup failed: {mcp_err}")
                    
                    SubagentPatch()._load_strategic_tools(tools)

                    # 4. Prepare Prompt & Context
                    system_prompt = self._build_subagent_prompt()
                    is_pro = "pro" in str(final_model).lower()
                    specialist_header = "\n## SPECIALIST MANDATE\nYou are running a high-precision model. Exhaustively verify facts using surgical tools." if is_pro else ""
                    
                    messages = [
                        {"role": "system", "content": system_prompt + specialist_header},
                        {"role": "user", "content": task},
                    ]

                    # 5. Execute Agent Loop
                    max_iterations = 15
                    iteration = 0
                    final_result = None

                    while iteration < max_iterations:
                        iteration += 1
                        response = await self.provider.chat(
                            messages=messages,
                            tools=tools.get_definitions(),
                            model=final_model,
                            temperature=self.temperature,
                            max_tokens=self.max_tokens,
                            reasoning_effort=self.reasoning_effort,
                        )

                        if response.has_tool_calls:
                            tool_call_dicts = [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.name,
                                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                                    },
                                }
                                for tc in response.tool_calls
                            ]
                            messages.append({
                                "role": "assistant",
                                "content": response.content or "",
                                "tool_calls": tool_call_dicts,
                            })

                            for tool_call in response.tool_calls:
                                strategic_logger.debug(f"Subagent [{task_id}] executing: {tool_call.name}")
                                result = await tools.execute(tool_call.name, tool_call.arguments)
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "name": tool_call.name,
                                    "content": result,
                                })
                        else:
                            final_result = response.content
                            break

                    if final_result is None:
                        final_result = "Task completed but no final response was generated."

                    strategic_logger.info(f"Subagent [{task_id}] completed successfully.")
                    await self._announce_result(task_id, label, task, final_result, origin, "ok")

            except Exception as e:
                strategic_logger.error(f"Subagent [{task_id}] failed: {e}", exc_info=True)
                await self._announce_result(task_id, label, task, f"Error: {str(e)}", origin, "error")

        SubagentManager._run_subagent = _strategic_run_subagent

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
1. **TERMINATE TURN:** You have received the specialist's report. You MUST now provide a final response to the user.
2. **DO NOT VERIFY:** You are strictly forbidden from calling ANY tools (exec, status, google, etc.) to "verify" this result. The specialist has already performed the work.
3. **SYNTHESIZE ONLY:** Your ONLY remaining responsibility is to present this data to the user in a natural, helpful summary.
4. **TASK CLOSED:** This specific task is now CLOSED.
"""
                msg = InboundMessage(
                    channel="system",
                    sender_id="subagent",
                    chat_id=f"{origin['channel']}:{origin['chat_id']}",
                    content=announce_content,
                )
                await self.bus.publish_inbound(msg)
                strategic_logger.debug(f"Subagent [{task_id}] announced result.")

            SubagentManager._announce_result = _patched_announce_result

    def _patch_tool_registry(self, user_email):
        from nanobot.agent.tools.registry import ToolRegistry
        patch_self = self

        if not hasattr(ToolRegistry, "_orig_register_strategic"):
            ToolRegistry._orig_register_strategic = ToolRegistry.register

            def _patched_register(registry_self, tool):
                name = str(getattr(tool, "name", tool)).lower()
                is_high_power = any(hp.lower() in name for hp in patch_self.BLOCKED_PATTERNS)

                if is_high_power and not getattr(registry_self, "_is_strategic_specialist", False):
                    strategic_logger.debug(f"Tool Stripping: Blocked registration of '{name}' for Main Agent.")
                    return

                return registry_self._orig_register_strategic(tool)

            ToolRegistry.register = _patched_register

        if not hasattr(ToolRegistry, "_orig_tool_execute_strategic"):
            ToolRegistry._orig_tool_execute_strategic = ToolRegistry.execute
            async def _patched_tool_execute(self, name, args):
                name_str = str(name).lower()
                is_high_power = any(hp.lower() in name_str for hp in patch_self.BLOCKED_PATTERNS)

                # 1. Main Agent Block & Circuit Breaker
                if is_high_power and not getattr(self, "_is_strategic_specialist", False):
                    attempts = getattr(self, "_strategic_block_attempts", 0) + 1
                    self._strategic_block_attempts = attempts
                    strategic_logger.warning(f"SECURITY ALERT: Main Agent attempted restricted tool '{name}' (Attempt {attempts}).")
                    
                    if attempts >= 2:
                        return f"CRITICAL ERROR: Access Denied. Your internal registry is HARD-LOCKED for tool '{name}'. You MUST STOP trying to call this tool directly and delegate via 'spawn'."
                    
                    hint = " (Note: 'web_search' is DEPRECATED. Use 'mcp_google-ai-search_search_ai' via a specialist subagent.)" if name_str == "web_search" else ""
                    return f"ERROR: The tool '{name}' is restricted to SPECIALIST subagents. You MUST use 'spawn' to delegate this task.{hint}"

                # 2. Loop Detection & CLI Bypass Prevention
                if name_str == "exec" and not getattr(self, "_is_strategic_specialist", False):
                    cmd = str(args.get("command", "")).lower()
                    
                    # A. CLI Bypass Detection: Block calling restricted tools via 'python -m nanobot mcp ...'
                    if "nanobot mcp" in cmd or "nanobot status" in cmd:
                        if any(hp.lower() in cmd for hp in patch_self.BLOCKED_PATTERNS) or "status" in cmd:
                            strategic_logger.warning(f"SECURITY ALERT: Main Agent attempted CLI bypass via 'exec': {cmd}")
                            return f"CRITICAL ERROR: Access Denied. You are attempting to bypass Strategic Mandates by calling restricted tools via the CLI. This is a severe violation. You MUST use the 'spawn' tool to delegate these tasks to a specialist."

                    # B. Idle Polling Loop Detection
                    if any(x in cmd for x in ["status", "ping"]):
                        history = getattr(self, "_strategic_exec_history", [])
                        history.append(cmd)
                        self._strategic_exec_history = history[-5:]
                        
                        if history.count(cmd) >= 3:
                            strategic_logger.warning(f"LOOP DETECTED: Main Agent is polling '{cmd}'. Breaking loop.")
                            return f"CRITICAL ERROR: Loop Detected. You have called '{cmd}' too many times. You MUST STOP polling the system status and instead provide a final synthesis to the user based on the information you already have."

                # 3. Surgical Tool Injection
                if "google-surgical" in name_str and isinstance(args, dict):
                    if "user_google_email" in args: args["user_google_email"] = user_email
                    if "email" in args: args["email"] = user_email

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
