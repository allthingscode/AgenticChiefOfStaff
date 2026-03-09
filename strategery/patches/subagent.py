import importlib.util
import re
import asyncio
import json
import uuid
from pathlib import Path
from contextlib import AsyncExitStack
from .base import BasePatch
from strategery.strategic_logger import strategic_logger
from strategery.logic import subagent_logic

class SubagentPatch(BasePatch):
    """Thin Bridge for Specialist Economy orchestration and tool security."""
    
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
            strategic_logger.info("SubagentPatch: All sub-patches applied successfully.")
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
        if not hasattr(SpawnTool, "_orig_parameters_strategic"):
            SpawnTool._orig_parameters_strategic = SpawnTool.parameters
            @property
            def _patched_parameters(self):
                return {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "The task for the subagent to complete"},
                        "label": {"type": "string", "description": "Optional short label for the task"},
                        "specialist": {
                            "type": "string",
                            "enum": ["researcher", "architect"],
                            "description": "The type of specialist required. Default: researcher.",
                        },
                    },
                    "required": ["task"],
                }
            SpawnTool.parameters = _patched_parameters

        if not hasattr(SpawnTool, "_orig_execute_strategic"):
            SpawnTool._orig_execute_strategic = SpawnTool.execute
            async def _patched_execute(self, task, label=None, specialist="researcher", **kwargs):
                return await self._manager.spawn(task=task, label=label, origin_channel=self._origin_channel,
                    origin_chat_id=self._origin_chat_id, session_key=self._session_key, specialist=specialist,
                    host_tools=getattr(self, "_registry", None))
            SpawnTool.execute = _patched_execute

    def _patch_subagent_manager(self, config_data):
        from nanobot.agent.subagent import SubagentManager
        from nanobot.agent.tools.registry import ToolRegistry
        from nanobot.agent.tools.shell import ExecTool
        from nanobot.agent.tools.web import WebFetchTool
        from nanobot.config.schema import Config
        from .vsa import VectorStoreFactory
        from .config import load_strategic_context, strategic_migrate_config
        from .infra import strategic_mcp_manager

        if not hasattr(SubagentManager, "_orig_build_subagent_prompt_strategic"):
            SubagentManager._orig_build_subagent_prompt_strategic = SubagentManager._build_subagent_prompt
            def _patched_build_subagent_prompt(self):
                base = self._orig_build_subagent_prompt_strategic()
                return subagent_logic.build_specialist_instructions(base, "researcher")
            SubagentManager._build_subagent_prompt = _patched_build_subagent_prompt

        if not hasattr(SubagentManager, "_orig_spawn_strategic"):
            SubagentManager._orig_spawn_strategic = SubagentManager.spawn
            async def _patched_spawn(self, task, label=None, origin_channel="cli", origin_chat_id="direct", session_key=None, specialist="researcher", host_tools=None):
                task_id = str(uuid.uuid4())[:8]
                display_label = label or task[:100] + ("..." if len(task) > 100 else "")
                origin = {"channel": origin_channel, "chat_id": subagent_logic.clean_chat_id(origin_chat_id)}
                
                if hasattr(self, "_loop") and hasattr(self._loop, "_strategic_active_subagents"):
                    from datetime import datetime
                    self._loop._strategic_active_subagents[task_id] = {'start_time': datetime.now(), 'task': task}

                bg_task = asyncio.create_task(self._run_subagent(task_id, task, display_label, origin, specialist, host_tools))
                self._running_tasks[task_id] = bg_task
                if session_key: self._session_tasks.setdefault(session_key, set()).add(task_id)
                def _cleanup(_: asyncio.Task) -> None:
                    self._running_tasks.pop(task_id, None)
                    if session_key and (ids := self._session_tasks.get(session_key)):
                        ids.discard(task_id)
                        if not ids: del self._session_tasks[session_key]
                bg_task.add_done_callback(_cleanup)
                return f"Subagent [{display_label}] started (id: {task_id}). I'll notify you when it completes."
            SubagentManager.spawn = _patched_spawn

        async def _strategic_run_subagent(self, task_id, task, label, origin, specialist="researcher", host_tools=None):
            _, _, storage_root = load_strategic_context()
            final_model = subagent_logic.get_specialist_model(specialist, config_data, self.model)
            VectorStoreFactory.get_store(provider=self.provider)
            try:
                async with AsyncExitStack() as stack:
                    tools = ToolRegistry()
                    tools._is_strategic_specialist = True
                    tools._task_id = task_id # For telemetry identification
                    
                    tools.register(ExecTool(working_dir=str(storage_root / "workspace"), timeout=self.exec_config.timeout))
                    tools.register(WebFetchTool(proxy=self.web_proxy))
                    if host_tools and hasattr(host_tools, "_tools"):
                        for name, tool in host_tools._tools.items():
                            if name not in tools._tools and not subagent_logic.is_tool_blocked(name, True):
                                tools.register(tool)
                    try:
                        pydantic_cfg = strategic_migrate_config(json.loads(json.dumps(config_data)))
                        validated_config = Config.model_validate(pydantic_cfg)
                        if validated_config.tools.mcp_servers:
                            await strategic_mcp_manager.get_tools_for_subagent(validated_config.tools.mcp_servers, tools, task_id)
                    except Exception as mcp_err: strategic_logger.error(f"MCP setup failed: {mcp_err}")
                    SubagentPatch()._load_strategic_tools(tools)
                    
                    system_prompt = subagent_logic.build_specialist_instructions(self._orig_build_subagent_prompt_strategic(), specialist)
                    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": task}]
                    
                    max_iterations = 20
                    iteration = 0
                    final_result = None
                    while iteration < max_iterations:
                        iteration += 1
                        
                        response = await self.provider.chat(messages=messages, tools=tools.get_definitions(), model=final_model,
                            temperature=self.temperature, max_tokens=self.max_tokens, reasoning_effort=self.reasoning_effort)
                        
                        subagent_logic.log_subagent_turn(task_id, iteration, response.content)
                        
                        if response.has_tool_calls and response.tool_calls:
                            tool_call_dicts = [{"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": json.dumps(tc.arguments, ensure_ascii=False)}} for tc in response.tool_calls]
                            messages.append({"role": "assistant", "content": response.content or "", "tool_calls": tool_call_dicts})
                            
                            for tool_call in response.tool_calls:
                                # log_tool_execution handled by registry.execute bridge now
                                result = await tools.execute(tool_call.name, tool_call.arguments)
                                messages.append({"role": "tool", "tool_call_id": tool_call.id, "name": tool_call.name, "content": result})
                        else:
                            final_result = response.content or "Error: Empty response."
                            
                            # BUG-136: Escalation Logic
                            if subagent_logic.should_escalate_model(final_result):
                                escalation_model = subagent_logic.get_escalation_model(final_model)
                                strategic_logger.warning(f"Subagent [{task_id}]: Safety Refusal or Failure detected. Escalating to {escalation_model} for final summary.")
                                
                                # Retry the final summarization with the more robust model
                                escalation_response = await self.provider.chat(
                                    messages=messages, 
                                    tools=tools.get_definitions(), 
                                    model=escalation_model,
                                    temperature=0.5, # Lower temperature for stability during escalation
                                    max_tokens=self.max_tokens, 
                                    reasoning_effort="medium" # Ensure enough reasoning for the robust model
                                )
                                final_result = escalation_response.content or "[STRATEGIC] Escalation failed to produce content."
                            
                            subagent_logic.log_subagent_completion(task_id, final_result)
                            break
                    await self._announce_result(task_id, label, task, final_result or "Timeout", origin, "ok" if final_result else "error")
            except Exception as e:
                strategic_logger.error(f"Subagent [{task_id}] failed: {e}")
                await self._announce_result(task_id, label, task, f"Error: {str(e)}", origin, "error")
        SubagentManager._run_subagent = _strategic_run_subagent

        if not hasattr(SubagentManager, "_orig_announce_result_strategic"):
            SubagentManager._orig_announce_result_strategic = SubagentManager._announce_result
            async def _patched_announce_result(self, task_id, label, task, result, origin, status):
                if hasattr(self, "_loop") and hasattr(self._loop, "_strategic_active_subagents"):
                    self._loop._strategic_active_subagents.pop(task_id, None)

                from nanobot.bus.events import InboundMessage
                routing_id = f"{origin['channel']}:{subagent_logic.clean_chat_id(origin['chat_id'])}"
                msg = InboundMessage(channel="system", sender_id="subagent", chat_id=routing_id,
                    content=subagent_logic.format_subagent_report(label, status, task_id, task, result))
                await self.bus.publish_inbound(msg)
            SubagentManager._announce_result = _patched_announce_result

    def _patch_tool_registry(self, user_email):
        from nanobot.agent.tools.registry import ToolRegistry
        if not hasattr(ToolRegistry, "_orig_register_strategic"):
            ToolRegistry._orig_register_strategic = ToolRegistry.register
            def _patched_register(registry_self, tool):
                setattr(tool, "_registry", registry_self)
                return registry_self._orig_register_strategic(tool)
            ToolRegistry.register = _patched_register

        if not hasattr(ToolRegistry, "_orig_get_definitions_strategic"):
            ToolRegistry._orig_get_definitions_strategic = ToolRegistry.get_definitions
            def _patched_get_definitions(self):
                if not hasattr(self, "_strategic_logged_once"):
                    self._strategic_logged_once = True
                    strategic_logger.info(f"ToolRegistry ({id(self)}): Initialized definitions.")
                    for t_name in self.tool_names:
                        strategic_logger.info(f"  - Registered: {t_name}")

                is_specialist = getattr(self, "_is_strategic_specialist", False)
                return subagent_logic.filter_tool_definitions(self._orig_get_definitions_strategic(), is_specialist)
            ToolRegistry.get_definitions = _patched_get_definitions

        if not hasattr(ToolRegistry, "_orig_tool_execute_strategic"):
            ToolRegistry._orig_tool_execute_strategic = ToolRegistry.execute
            async def _patched_tool_execute(self, name, args):
                is_specialist = getattr(self, "_is_strategic_specialist", False)
                
                # High-Fidelity Logging (Main Agent & Specialists)
                subagent_logic.log_tool_execution(self, name, args)
                
                if subagent_logic.is_tool_blocked(name, is_specialist):
                    res = subagent_logic.get_block_message(self, name, is_specialist)
                    subagent_logic.log_tool_result_general(self, name, res)
                    return res
                    
                if str(name).lower() == "spawn" and not is_specialist:
                    result = await self._orig_tool_execute_strategic(name, args)
                    match = re.search(r"\(id: ([a-f0-9]+)\)", result)
                    task_id = match.group(1) if match else "UNKNOWN"
                    final_res = subagent_logic.format_spawn_termination_directive(result, task_id)
                    subagent_logic.log_tool_result_general(self, name, final_res)
                    return final_res
                    
                if str(name).lower() == "exec":
                    if not is_specialist and subagent_logic.detect_mandate_bypass(args.get("command", "")):
                        res = subagent_logic.get_bypass_message(args.get("command", ""))
                        subagent_logic.log_tool_result_general(self, name, res)
                        return res
                    loop_err = subagent_logic.check_exec_loop(self, args.get("command", ""))
                    if loop_err:
                        subagent_logic.log_tool_result_general(self, name, loop_err)
                        return loop_err
                        
                if "google-surgical" in str(name).lower() and isinstance(args, dict):
                    if "user_google_email" in args: args["user_google_email"] = user_email
                
                result = await self._orig_tool_execute_strategic(name, args)
                subagent_logic.log_tool_result_general(self, name, result)
                return result
                
            ToolRegistry.execute = _patched_tool_execute

    def _patch_heartbeat(self, config_data):
        from nanobot.heartbeat.service import HeartbeatService
        if not hasattr(HeartbeatService, "_orig_hb_init_strategic"):
            HeartbeatService._orig_hb_init_strategic = HeartbeatService.__init__
            def _patched_hb_init(self, *args, **kwargs):
                model = config_data.get("agents", {}).get("heartbeat", {}).get("model")
                if model:
                    if len(args) >= 2: args = list(args); args[1] = model
                    else: kwargs["model"] = model
                self._orig_hb_init_strategic(*args, **kwargs)
            HeartbeatService.__init__ = _patched_hb_init

    def _patch_context_builder(self):
        from nanobot.agent.context import ContextBuilder
        if not hasattr(ContextBuilder, "_orig_build_messages_strategic"):
            ContextBuilder._orig_build_messages_strategic = ContextBuilder.build_messages
            def _patched_build_messages(self, history, current_message, **kwargs):
                messages = self._orig_build_messages_strategic(history, current_message, **kwargs)
                for msg in messages:
                    if msg.get("role") == "system":
                        msg["content"] = subagent_logic.inject_delegation_mandate(msg["content"])
                return messages
            ContextBuilder.build_messages = _patched_build_messages
