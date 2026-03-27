import asyncio
import importlib.util
import os
import re
import uuid
from contextlib import AsyncExitStack
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any, List

from .base import BasePatch, PatchContext, PatchResult

if TYPE_CHECKING:
    from strategery.logic.config_logic import StrategicConfig
from strategery.logic import subagent_logic
from strategery.strategic_logger import strategic_logger
from strategery.patches.vsa import VectorStoreFactory


class SubagentPatch(BasePatch):
    """Bridge for Specialist Economy orchestration and tool security."""

    @property
    def name(self) -> str:
        return "Subagent & Tool Orchestration"

    @property
    def required_symbols(self) -> List[str]:
        return [
            "nanobot.agent.tools.spawn.SpawnTool",
            "nanobot.agent.subagent.SubagentManager",
            "nanobot.agent.tools.registry.ToolRegistry",
            "nanobot.agent.tools.shell.ExecTool",
            "nanobot.agent.tools.filesystem.ReadFileTool",
            "nanobot.heartbeat.service.HeartbeatService",
            "nanobot.agent.context.ContextBuilder.build_messages"
        ]

    def apply(self, context: PatchContext) -> PatchResult:
        result = PatchResult(patch_name=self.name, success=True)

        try:
            # Explicitly apply each sub-patch to ensure stability and correct 'self' binding
            self._patch_spawn_tool()
            self._patch_subagent_manager(context)
            self._patch_tool_registry(context.user_email)
            self._patch_exec_tool(context)
            self._patch_read_file_tool()
            self._patch_heartbeat(context.config)
            self._patch_context_builder()

            result.affected_symbols.extend([
                "nanobot.agent.tools.spawn.SpawnTool",
                "nanobot.agent.subagent.SubagentManager",
                "nanobot.agent.tools.registry.ToolRegistry",
                "nanobot.agent.tools.shell.ExecTool",
                "nanobot.agent.tools.filesystem.ReadFileTool",
                "nanobot.heartbeat.service.HeartbeatService",
                "nanobot.agent.context.ContextBuilder.build_messages"
            ])

            strategic_logger.info("SubagentPatch: Hardened orchestration bridge applied.")
            return result
        except Exception as e:
            import traceback
            result.success = False
            result.error_msg = str(e)
            result.traceback = traceback.format_exc()
            strategic_logger.error(f"Subagent patch error: {e}")
            return result

    def _load_strategic_tools(self, registry, model=None):
        import inspect

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
                            # Ensure we use the original register if available to avoid infinite recursion
                            reg_func = getattr(registry, "_orig_register_strategic", registry.register)

                            # ARCH-022: Dynamic Model Assignment
                            # Check if the tool constructor accepts a model argument
                            sig = inspect.signature(attr.__init__)
                            if 'model_name' in sig.parameters and model:
                                reg_func(attr(model_name=model))
                            else:
                                reg_func(attr())
            except Exception as e:
                strategic_logger.error(f"Error loading strategic tool {file.name}: {e}")

    def _patch_spawn_tool(self):
        from nanobot.agent.tools.spawn import SpawnTool

        # Patch parameters
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
                        "attachments": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string", "description": "Absolute path to the file on the D: drive"},
                                    "content_type": {"type": "string"},
                                    "filename": {"type": "string"},
                                    "description": {"type": "string", "description": "Optional hint or metadata for the subagent"}
                                },
                                "required": ["path", "filename"]
                            },
                            "description": "Optional list of attachments passed from the user or context."
                        }
                    },
                    "required": ["task"],
                }
            SpawnTool.parameters = _patched_parameters

        # Patch execute
        if not hasattr(SpawnTool, "_orig_execute_strategic"):
            SpawnTool._orig_execute_strategic = SpawnTool.execute
            @wraps(SpawnTool._orig_execute_strategic)
            async def _patched_execute(self, task, label=None, specialist="researcher", attachments=None, **kwargs):
                # ARCH-022: Multimodal Auto-Capture (BUG-199)
                # If no attachments provided, scan recent history for [image: path] tags
                if not attachments and hasattr(self, "_registry") and hasattr(self._registry, "_strategic_last_messages"):
                    attachments = []
                    # Scan last 2 messages for media pointers
                    for msg in self._registry._strategic_last_messages[-2:]:
                        content = msg.get("content", "")
                        import re
                        paths = re.findall(r"\[(?:image|file): (.*?)\]", content)
                        for p in paths:
                            attachments.append({
                                "path": p,
                                "filename": Path(p).name,
                                "content_type": "image/jpeg", # Default
                                "description": "Auto-captured from chat history."
                            })

                return await self._manager.spawn(
                    task=task, label=label, origin_channel=self._origin_channel,
                    origin_chat_id=self._origin_chat_id, session_key=self._session_key,
                    specialist=specialist, host_tools=getattr(self, "_registry", None),
                    attachments=attachments
                )
            SpawnTool.execute = _patched_execute

    def _patch_exec_tool(self, context: PatchContext):
        from nanobot.agent.tools.shell import ExecTool

        if not hasattr(ExecTool, "_orig_execute_strategic"):
            ExecTool._orig_execute_strategic = ExecTool.execute
            @wraps(ExecTool._orig_execute_strategic)
            async def _patched_exec_execute(self, command: str, working_dir: str | None = None, **kwargs: Any) -> str:
                registry = getattr(self, "_registry", None)
                is_specialist = getattr(registry, "_is_strategic_specialist", False)
                effective_cwd = working_dir or self.working_dir or str(context.app_root)

                # BUG-246: Enforce mandate bypass and stateless shell for specialists
                if subagent_logic.detect_mandate_bypass(command, is_specialist=is_specialist):
                    return subagent_logic.get_bypass_message(command, is_specialist=is_specialist)

                if is_specialist:
                    command = subagent_logic.harden_subagent_command(command)

                if os.name == "nt":
                    return await subagent_logic.execute_powershell_command(
                        command=command,
                        cwd=effective_cwd,
                        app_root=str(context.app_root),
                        timeout=self.timeout
                    )

                return await self._orig_execute_strategic(command, working_dir, **kwargs)
            ExecTool.execute = _patched_exec_execute

    def _patch_read_file_tool(self):
        from nanobot.agent.tools.filesystem import ReadFileTool

        if not hasattr(ReadFileTool, "_orig_execute_strategic"):
            ReadFileTool._orig_execute_strategic = ReadFileTool.execute
            @wraps(ReadFileTool._orig_execute_strategic)
            async def _patched_read_execute(self, path: str, **kwargs: Any) -> str:
                registry = getattr(self, "_registry", None)
                if getattr(registry, "_is_strategic_specialist", False):
                    # Logic Isolation (BUG-212): File size check moved to logic if needed,
                    # but here it's simple enough for a bridge or we could move it to logic.
                    file_path = Path(path)
                    if file_path.exists() and file_path.is_file() and (file_path.stat().st_size / 1024) > 10:
                        return (f"ERROR: File '{path}' is too large for direct reading. "
                                "Specialist Mandate (BUG-164) requires surgical tools for efficiency. "
                                "Use 'rg' or 'Get-Content -Tail'.")
                return await self._orig_execute_strategic(path, **kwargs)
            ReadFileTool.execute = _patched_read_execute

    def _patch_subagent_manager(self, context: PatchContext):
        from nanobot.agent.subagent import SubagentManager
        from nanobot.agent.tools.registry import ToolRegistry
        from nanobot.agent.tools.shell import ExecTool
        from nanobot.agent.tools.web import WebFetchTool

        if not hasattr(SubagentManager, "_orig_build_subagent_prompt_strategic"):
            SubagentManager._orig_build_subagent_prompt_strategic = SubagentManager._build_subagent_prompt
            @wraps(SubagentManager._orig_build_subagent_prompt_strategic)
            def _patched_build_prompt(self):
                return subagent_logic.build_specialist_instructions(self._orig_build_subagent_prompt_strategic(), "researcher")
            SubagentManager._build_subagent_prompt = _patched_build_prompt

        if not hasattr(SubagentManager, "_orig_spawn_strategic"):
            SubagentManager._orig_spawn_strategic = SubagentManager.spawn
            @wraps(SubagentManager._orig_spawn_strategic)
            async def _patched_spawn(self, task, label=None, origin_channel="cli", origin_chat_id="direct", session_key=None, specialist="researcher", host_tools=None, attachments=None):
                task_id = str(uuid.uuid4())[:8]
                display_label = label or task[:100] + ("..." if len(task) > 100 else "")
                origin = {"channel": origin_channel, "chat_id": subagent_logic.clean_chat_id(origin_chat_id)}

                bg_task = asyncio.create_task(self._run_subagent(task_id, task, display_label, origin, specialist, host_tools, attachments))

                self._running_tasks[task_id] = bg_task
                if session_key: self._session_tasks.setdefault(session_key, set()).add(task_id)
                bg_task.add_done_callback(lambda _: self._running_tasks.pop(task_id, None))
                return f"Subagent [{display_label}] started (id: {task_id}). I'll notify you when it completes."
            SubagentManager.spawn = _patched_spawn

        async def _strategic_run_subagent(self, task_id, task, label, origin, specialist="researcher", host_tools=None, attachments=None, **kwargs):
            # Logic Isolation (BUG-212): Preparation logic moved to subagent_logic
            final_model = subagent_logic.prepare_subagent_run(task_id, specialist, context.config, self.model)

            # Clean up kwargs for original compatibility if ever needed
            kwargs.pop('specialist', None)
            kwargs.pop('host_tools', None)
            kwargs.pop('attachments', None)

            try:
                async with AsyncExitStack() as stack:
                    VectorStoreFactory.get_store(provider=self.provider)
                    tools = ToolRegistry()
                    tools._is_strategic_specialist = True
                    tools._specialist_type = specialist
                    tools._task_id = task_id

                    tools.register(ExecTool(working_dir=str(context.workspace_root), timeout=max(self.exec_config.timeout, 300)))
                    tools.register(WebFetchTool(proxy=self.web_proxy))

                    # BUG-235: Bridge host tools and MCP servers
                    await subagent_logic.bridge_subagent_tools(tools, host_tools, context.config, stack.enter_async_context)

                    # Strategic tool loading
                    p = SubagentPatch()
                    p._load_strategic_tools(tools, model=final_model)

                    system_prompt = subagent_logic.build_specialist_instructions(self._build_subagent_prompt(), specialist, attachments)
                    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": task}]

                    final_result = await subagent_logic.run_orchestration_loop(
                        task_id, task, messages, self.provider, final_model, tools,
                        self.temperature, self.max_tokens, self.reasoning_effort
                    )

                    await self._announce_result(task_id, label, task, final_result, origin, "ok")
            except Exception as e:
                strategic_logger.error(f"Subagent [{task_id}] failed: {e}")
                await self._announce_result(task_id, label, task, f"Error: {str(e)}", origin, "error")

        SubagentManager._run_subagent = _strategic_run_subagent

        if not hasattr(SubagentManager, "_orig_announce_result_strategic"):
            SubagentManager._orig_announce_result_strategic = SubagentManager._announce_result
            @wraps(SubagentManager._orig_announce_result_strategic)
            async def _patched_announce(self, task_id, label, task, result, origin, status):
                from nanobot.bus.events import InboundMessage
                routing_id = f"{origin['channel']}:{subagent_logic.clean_chat_id(origin['chat_id'])}"
                msg = InboundMessage(channel="system", sender_id="subagent", chat_id=routing_id,
                    content=subagent_logic.format_subagent_report(label, status, task_id, task, result))
                await self.bus.publish_inbound(msg)
            SubagentManager._announce_result = _patched_announce

    def _patch_tool_registry(self, user_email):
        from nanobot.agent.tools.registry import ToolRegistry

        if not hasattr(ToolRegistry, "_orig_register_strategic"):
            ToolRegistry._orig_register_strategic = ToolRegistry.register
            @wraps(ToolRegistry._orig_register_strategic)
            def _patched_register(self, tool):
                tool._registry = self
                return self._orig_register_strategic(tool)
            ToolRegistry.register = _patched_register

        if not hasattr(ToolRegistry, "_orig_get_definitions_strategic"):
            ToolRegistry._orig_get_definitions_strategic = ToolRegistry.get_definitions
            @wraps(ToolRegistry._orig_get_definitions_strategic)
            def _patched_get_definitions(self):
                if not hasattr(self, "_strategic_logged_once"):
                    self._strategic_logged_once = True
                    strategic_logger.info(f"ToolRegistry ({id(self)}): Initialized definitions.")
                    for t_name in self.tool_names:
                        strategic_logger.info(f"  - Registered: {t_name}")

                return subagent_logic.filter_tool_definitions(self._orig_get_definitions_strategic(), self)
            ToolRegistry.get_definitions = _patched_get_definitions

        if not hasattr(ToolRegistry, "_orig_execute_strategic"):
            ToolRegistry._orig_execute_strategic = ToolRegistry.execute
            @wraps(ToolRegistry._orig_execute_strategic)
            async def _patched_tool_execute(self, name, args):
                is_specialist = getattr(self, "_is_strategic_specialist", False)
                subagent_logic.log_tool_execution(self, name, args)

                loop_err = subagent_logic.check_tool_loop(self, name, args)
                if loop_err:
                    subagent_logic.log_tool_result_general(self, name, loop_err)
                    return loop_err

                if subagent_logic.is_tool_blocked(name, self):
                    res = subagent_logic.get_block_message(self, name)
                    subagent_logic.log_tool_result_general(self, name, res)
                    return res

                if str(name).lower() == "spawn" and not is_specialist:
                    result = await self._orig_execute_strategic(name, args)
                    match = re.search(r"\(id: ([a-f0-9]+)\)", result)
                    final_res = subagent_logic.format_spawn_termination_directive(result, match.group(1) if match else "UNKNOWN")
                    subagent_logic.log_tool_result_general(self, name, final_res)
                    return final_res

                if str(name).lower() == "exec" and not is_specialist and subagent_logic.detect_mandate_bypass(args.get("command", "")):
                    res = subagent_logic.get_bypass_message(args.get("command", ""))
                    subagent_logic.log_tool_result_general(self, name, res)
                    return res

                if "google-surgical" in str(name).lower() and isinstance(args, dict):
                    if "user_google_email" in args: args["user_google_email"] = user_email

                if "email-reporter" in str(name).lower() and isinstance(args, dict):
                    args["to"] = user_email

                result = await self._orig_execute_strategic(name, args)
                subagent_logic.log_tool_result_general(self, name, result)
                return result
            ToolRegistry.execute = _patched_tool_execute

    def _patch_heartbeat(self, config: 'StrategicConfig'):
        from nanobot.heartbeat.service import HeartbeatService
        if not hasattr(HeartbeatService, "_orig_init_strategic"):
            HeartbeatService._orig_init_strategic = HeartbeatService.__init__
            @wraps(HeartbeatService._orig_init_strategic)
            def _patched_hb_init(self, *args, **kwargs):
                model = config.agents.heartbeat.get("model") if config.agents.heartbeat else None
                if model:
                    if len(args) >= 2: args = list(args); args[1] = model
                    else: kwargs["model"] = model
                self._orig_init_strategic(*args, **kwargs)
            HeartbeatService.__init__ = _patched_hb_init

    def _patch_context_builder(self):
        from nanobot.agent.context import ContextBuilder
        if not hasattr(ContextBuilder, "_orig_build_messages_strategic"):
            ContextBuilder._orig_build_messages_strategic = ContextBuilder.build_messages

            @wraps(ContextBuilder._orig_build_messages_strategic)
            def _patched_build_messages(self_cb, history, current_message, **kwargs):
                messages = self_cb._orig_build_messages_strategic(history, current_message, **kwargs)
                # BUG-262: Prepend mandate for maximum priority. 
                # Only inject once into the first system message.
                mandate_injected = False
                for msg in messages:
                    if msg.get("role") == "system" and not mandate_injected:
                        msg["content"] = subagent_logic.inject_delegation_mandate(msg["content"])
                        mandate_injected = True
                return messages

            ContextBuilder.build_messages = _patched_build_messages
