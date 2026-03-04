import sys
import os
import importlib.util
import re
import asyncio
import json
import uuid
from pathlib import Path
from .base import BasePatch
from strategery.strategic_logger import strategic_logger

class SubagentPatch(BasePatch):
    """
    Enforces a Specialist Economy:
    - High-power tools are BLOCKED from the Main Agent.
    - Subagents are granted Surgical Tools (including MCP) and assigned specialist models.
    - Dynamic Specialist Routing: Orchestrator chooses 'researcher' or 'architect'.
    - Specialist models are strictly tied to type; Orchestrator cannot dictate models.
    - Turn termination is ENFORCED after subagent spawn.
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
            self._patch_spawn_tool()
            self._patch_subagent_manager(config_data)
            self._patch_tool_registry(user_email)
            self._patch_heartbeat(config_data)
            self._patch_context_builder()
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
                            reg_func = getattr(registry, "_orig_register_strategic", registry.register)
                            reg_func(attr())
            except Exception as e:
                strategic_logger.error(f"Error loading strategic tool {file.name}: {e}")

    def _patch_spawn_tool(self):
        from nanobot.agent.tools.spawn import SpawnTool
        
        # 1. Update Tool Definition with 'specialist' parameter
        if not hasattr(SpawnTool, "_orig_parameters_strategic"):
            SpawnTool._orig_parameters_strategic = SpawnTool.parameters
            
            @property
            def _patched_parameters(self):
                return {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "The task for the subagent to complete",
                        },
                        "label": {
                            "type": "string",
                            "description": "Optional short label for the task (for display)",
                        },
                        "specialist": {
                            "type": "string",
                            "enum": ["researcher", "architect"],
                            "description": "The type of specialist required. Default: researcher. Use 'architect' for design, NanoGraph, or complex reasoning.",
                        },
                    },
                    "required": ["task"],
                }

            SpawnTool.parameters = _patched_parameters

        # 2. Update Tool Execution to pass 'specialist'
        if not hasattr(SpawnTool, "_orig_execute_strategic"):
            SpawnTool._orig_execute_strategic = SpawnTool.execute
            
            async def _patched_execute(self, task: str, label: str | None = None, specialist: str = "researcher", **kwargs):
                # Ensure specialist is one of the allowed types, otherwise default to researcher
                if specialist not in ["researcher", "architect"]:
                    specialist = "researcher"
                    
                return await self._manager.spawn(
                    task=task,
                    label=label,
                    origin_channel=self._origin_channel,
                    origin_chat_id=self._origin_chat_id,
                    session_key=self._session_key,
                    specialist=specialist
                )
            
            SpawnTool.execute = _patched_execute

    def _patch_subagent_manager(self, config_data):
        from nanobot.agent.subagent import SubagentManager
        from nanobot.agent.tools.registry import ToolRegistry
        from nanobot.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
        from nanobot.agent.tools.shell import ExecTool
        from nanobot.agent.tools.web import WebFetchTool
        from nanobot.config.schema import Config
        from contextlib import AsyncExitStack

        # 1. Update spawn signature to accept specialist type
        if not hasattr(SubagentManager, "_orig_spawn_strategic"):
            SubagentManager._orig_spawn_strategic = SubagentManager.spawn
            
            async def _patched_spawn(self, task, label=None, origin_channel="cli", origin_chat_id="direct", session_key=None, specialist="researcher"):
                task_id = str(uuid.uuid4())[:8]
                display_label = label or task[:100] + ("..." if len(task) > 100 else "")
                origin = {"channel": origin_channel, "chat_id": origin_chat_id}

                bg_task = asyncio.create_task(
                    self._run_subagent(task_id, task, display_label, origin, specialist)
                )
                self._running_tasks[task_id] = bg_task
                if session_key:
                    self._session_tasks.setdefault(session_key, set()).add(task_id)

                def _cleanup(_: asyncio.Task) -> None:
                    self._running_tasks.pop(task_id, None)
                    if session_key and (ids := self._session_tasks.get(session_key)):
                        ids.discard(task_id)
                        if not ids:
                            del self._session_tasks[session_key]

                bg_task.add_done_callback(_cleanup)
                strategic_logger.info(f"Spawned subagent [{task_id}]: {display_label} (specialist={specialist})")
                return f"Subagent [{display_label}] started (id: {task_id}). I'll notify you when it completes."

            SubagentManager.spawn = _patched_spawn

        # 2. Replace the entire _run_subagent to inject MCP and Specialist Logic
        async def _strategic_run_subagent(self, task_id, task, label, origin, specialist="researcher"):
            from .config import load_strategic_context
            _, _, storage_root = load_strategic_context()
            strategic_workspace = storage_root / "workspace"

            strategic_logger.info(f"Subagent [{task_id}] starting task: {label}")
            
            # Specialist model selection from config
            specialists_cfg = config_data.get("agents", {}).get("specialists", {})
            # Default to researcher if specialist is invalid
            if specialist not in ["researcher", "architect"]:
                specialist = "researcher"
                
            selected_model = specialists_cfg.get(specialist, {}).get("model")
            
            # Final fallback to manager default model if config is missing
            final_model = selected_model or self.model
            strategic_logger.info(f"Subagent Specialist Assigned: {specialist} (model='{final_model}')")

            try:
                async with AsyncExitStack() as stack:
                    tools = ToolRegistry()
                    tools._is_strategic_specialist = True
                    
                    # MANDATE: Subagents MUST use the strategic workspace root on D:
                    subagent_workspace = strategic_workspace
                    allowed_dir = subagent_workspace if self.restrict_to_workspace else None
                    
                    tools.register(ReadFileTool(workspace=subagent_workspace, allowed_dir=allowed_dir))
                    tools.register(WriteFileTool(workspace=subagent_workspace, allowed_dir=allowed_dir))
                    tools.register(EditFileTool(workspace=subagent_workspace, allowed_dir=allowed_dir))
                    tools.register(ListDirTool(workspace=subagent_workspace, allowed_dir=allowed_dir))
                    tools.register(ExecTool(
                        working_dir=str(subagent_workspace),
                        timeout=self.exec_config.timeout,
                        restrict_to_workspace=self.restrict_to_workspace,
                        path_append=self.exec_config.path_append,
                    ))
                    tools.register(WebFetchTool(proxy=self.web_proxy))
                    
                    try:
                        from .config import strategic_migrate_config
                        from .infra import strategic_mcp_manager
                        pydantic_cfg = strategic_migrate_config(json.loads(json.dumps(config_data)))
                        validated_config = Config.model_validate(pydantic_cfg)
                        mcp_configs = validated_config.tools.mcp_servers
                        if mcp_configs:
                            await strategic_mcp_manager.get_tools_for_subagent(mcp_configs, tools, task_id)
                    except Exception as mcp_err:
                        strategic_logger.error(f"Subagent [{task_id}] MCP setup failed: {mcp_err}")
                    
                    SubagentPatch()._load_strategic_tools(tools)

                    system_prompt = self._build_subagent_prompt()
                    is_pro = "pro" in str(final_model).lower()
                    specialist_header = f"\n## {specialist.upper()} SPECIALIST MANDATE\nYou are running a high-precision model. Exhaustively verify facts using surgical tools."
                    
                    messages = [
                        {"role": "system", "content": system_prompt + specialist_header},
                        {"role": "user", "content": task},
                    ]

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
                            if response.finish_reason == "error":
                                raise Exception(f"Subagent LLM Error: {final_result}")
                            break

                    if final_result is None:
                        raise Exception(f"Subagent Task Timeout: No final response generated after {max_iterations} iterations.")

                    strategic_logger.info(f"Subagent [{task_id}] completed successfully.")
                    await self._announce_result(task_id, label, task, final_result, origin, "ok")

            except Exception as e:
                strategic_logger.error(f"Subagent [{task_id}] failed: {e}", exc_info=True)
                await self._announce_result(task_id, label, task, f"Error: {str(e)}", origin, "error")

        SubagentManager._run_subagent = _strategic_run_subagent

        if not hasattr(SubagentManager, "_orig_build_subagent_prompt_strategic"):
            SubagentManager._orig_build_subagent_prompt_strategic = SubagentManager._build_subagent_prompt
            
            def _patched_build_subagent_prompt(self):
                prompt = self._orig_build_subagent_prompt_strategic()

                # Append Strategic Specialist Instructions
                prompt += "\n\n## 🛡️ STRATEGIC SPECIALIST INSTRUCTIONS\n"
                prompt += "1. **SEARCH MANDATE:** Use 'mcp_google-ai-search_search_ai' for all web research. The 'web_search' tool is deprecated.\n"
                prompt += "2. **NETWORK DIAGNOSTICS:** Do NOT use 'ping' via 'exec'. It fails with 'Access denied' on this environment. Assume network connectivity is ACTIVE for MCP and LLM calls.\n"
                prompt += "3. **MEMORY ACCESS (D: DRIVE):** Long-term memory and conversation journals are stored at `D:\\Nanobot_Storage\\workspace\\memory`. You MUST use ABSOLUTE PATHS for all file operations (e.g., `D:\\Nanobot_Storage\\workspace\\memory\\MEMORY.md`). The file `HISTORY.md` is RETIRED.\n"
                prompt += "4. **CALENDAR MANDATE:** When asked about scheduling, appointments, or events for 'today' or 'tomorrow', you MUST use the `mcp_google-surgical_list_calendar_events` tool with `calendar_id='all'` to ensure you capture events from all sub-calendars.\n"
                prompt += "5. **SURGICAL PRECISION:** Exhaustively verify facts. Use 'read_file' to examine project configuration or history if needed.\n"
                return prompt

            SubagentManager._build_subagent_prompt = _patched_build_subagent_prompt

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
                is_specialist = getattr(registry_self, "_is_strategic_specialist", False)

                if is_high_power:
                    if not is_specialist:
                        strategic_logger.debug(f"Tool Stripping: Blocked registration of '{name}' for Main Agent.")
                        return
                    else:
                        strategic_logger.debug(f"Tool Stripping: ALLOWED registration of '{name}' for Specialist.")

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

                # 2. Forced Turn Termination for 'spawn'
                if name_str == "spawn" and not getattr(self, "_is_strategic_specialist", False):
                    # Call original execute to perform the spawn
                    result = await self._orig_tool_execute_strategic(name, args)
                    # Append Strategic Termination Directive
                    return f"{result}\n\n### ⚖️ STRATEGIC MANDATE: STOP Turn\nYou have successfully spawned a specialist. Your turn is now OVER. You MUST NOT call any more tools (like findstr or status) to poll for the result. Wait for the subagent to report back via the message bus. Provide a short acknowledgement to the user now and END your response."

                # 3. Loop Detection & CLI/File Bypass Prevention
                is_specialist = getattr(self, "_is_strategic_specialist", False)
                if name_str == "exec" and not is_specialist:
                    cmd = str(args.get("command", "")).lower()
                    
                    # A. CLI/File Bypass Detection
                    bypass_patterns = [
                        "nanobot mcp", "nanobot status", "history.md", "findstr", 
                        "grep", "cat ", "type ", "tail ", "get-content"
                    ]
                    if any(p in cmd for p in bypass_patterns):
                        strategic_logger.warning(f"SECURITY ALERT: Main Agent attempted Mandate Bypass via 'exec': {cmd}")
                        return f"CRITICAL ERROR: Access Denied. You are attempting to bypass Strategic Mandates (e.g. by polling HISTORY.md or calling the CLI directly). This is a severe violation. You MUST STOP and wait for the subagent to report back. HISTORY.md is RETIRED; use the message bus."

                    # B. Idle Polling Loop Detection (ping, status, etc.)
                    if any(x in cmd for x in ["status", "ping"]):
                        history = getattr(self, "_strategic_exec_history", [])
                        history.append(cmd)
                        self._strategic_exec_history = history[-5:]
                        
                        if history.count(cmd) >= 3:
                            strategic_logger.warning(f"LOOP DETECTED: Main Agent is polling '{cmd}'. Breaking loop.")
                            return f"CRITICAL ERROR: Loop Detected. You have called '{cmd}' too many times. You MUST STOP polling the system and instead provide a final synthesis to the user based on the information you already have."

                # 4. Surgical Tool Injection
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

    def _patch_context_builder(self):
        from nanobot.agent.context import ContextBuilder
        if not hasattr(ContextBuilder, "_orig_build_messages_strategic"):
            ContextBuilder._orig_build_messages_strategic = ContextBuilder.build_messages
            
            def _patched_build_messages(self, history, current_message, **kwargs):
                messages = self._orig_build_messages_strategic(history, current_message, **kwargs)
                
                # Identify System Message
                for msg in messages:
                    if msg.get("role") == "system":
                        msg["content"] += "\n\n## ⚖️ DELEGATION & SPECIALIST ECONOMY\n"
                        msg["content"] += "1. **DELEGATE BY DEFAULT:** For any background, research, or complex architectural task, use the 'spawn' tool.\n"
                        msg["content"] += "2. **CHOOSE YOUR SPECIALIST:**\n"
                        msg["content"] += "   - **'researcher' (DEFAULT):** Use for general facts, search, data collection, and simple file operations.\n"
                        msg["content"] += "   - **'architect':** Use for design, NanoGraph extraction, high-level structural planning, or complex reasoning.\n"
                        msg["content"] += "3. **NO MODEL CONTROL:** You choose the TYPE of specialist, but you have NO say in which AI model is used. The system handles model assignment automatically.\n"
                        msg["content"] += "4. **WHEN IN DOUBT, ASK:** If the task's complexity is unclear or the specialist choice is not obvious, STOP and ask the user for a directive.\n"
                        msg["content"] += "5. **STOP AFTER SPAWN:** Once you call 'spawn', your turn is OVER. Provide a brief acknowledgement and end your response."
                
                return messages
                
            ContextBuilder.build_messages = _patched_build_messages
