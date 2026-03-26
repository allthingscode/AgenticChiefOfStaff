"""
STRATEGIC CHECKPOINT PATCH: Durable Execution Bridge (ARCH-024)
Goal: Inject CheckpointManager into AgentLoop and SubagentManager.
Mandate: Zero Core Pollution.
"""
import functools
import json
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, Any, List

from loguru import logger

from strategery.logic import subagent_logic
from strategery.logic.checkpoint_logic import get_checkpoint_manager
from strategery.patches.base import BasePatch, PatchContext

if TYPE_CHECKING:
    pass

class CheckpointPatch(BasePatch):
    """Patches AgentLoop and SubagentManager for State Checkpointing."""

    @property
    def name(self) -> str:
        return "Checkpoint"

    required_symbols = ["AgentLoop", "SubagentManager"]

    def apply(self, context: PatchContext):
        try:
            manager = get_checkpoint_manager(context.storage_root)

            # 1. Patch AgentLoop._run_agent_loop
            self._patch_agent_loop(manager, context)

            # 2. Patch SubagentManager._run_subagent
            self._patch_subagent_manager(manager, context)

            # 3. Patch AgentLoop._process_message to handle Thread ID
            self._patch_process_message(manager, context)

            from strategery.patches.base import PatchResult
            return PatchResult(patch_name=self.name, success=True)
        except Exception as e:
            import traceback
            logger.error(f"Checkpoint patch application failed: {e}\n{traceback.format_exc()}")
            from strategery.patches.base import PatchResult
            return PatchResult(patch_name=self.name, success=False, error_msg=str(e))

    def _patch_agent_loop(self, manager, context: PatchContext):
        from nanobot.agent.loop import AgentLoop
        original_run_loop = AgentLoop._run_agent_loop

        @functools.wraps(original_run_loop)
        async def patched_run_loop(self_loop, initial_messages, on_progress=None):
            # Capture Thread ID from metadata if set
            thread_id = getattr(self_loop, "_current_thread_id", None)

            async def _checkpoint_step(msgs, it):
                if thread_id:
                    manager.save_snapshot(thread_id, it, msgs)

            # Re-implementing the core loop logic to inject checkpoints at start/after tool
            messages = initial_messages
            iteration = 0
            final_content = None
            tools_used: List[str] = []

            while iteration < self_loop.max_iterations:
                iteration += 1

                # CHECKPOINT: Start of iteration
                await _checkpoint_step(messages, iteration)

                response = await self_loop.provider.chat(
                    messages=messages,
                    tools=self_loop.tools.get_definitions(),
                    model=self_loop.model,
                    temperature=self_loop.temperature,
                    max_tokens=self_loop.max_tokens,
                    reasoning_effort=self_loop.reasoning_effort,
                )

                if response.has_tool_calls:
                    if on_progress:
                        thought = self_loop._strip_think(response.content)
                        if thought: await on_progress(thought)
                        await on_progress(self_loop._tool_hint(response.tool_calls), tool_hint=True)

                    tool_call_dicts = [
                        {
                            "id": tc.id, "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments, ensure_ascii=False)
                            }
                        } for tc in response.tool_calls
                    ]
                    messages = self_loop.context.add_assistant_message(
                        messages, response.content, tool_call_dicts,
                        reasoning_content=response.reasoning_content,
                        thinking_blocks=response.thinking_blocks,
                    )

                    for tool_call in response.tool_calls:
                        tools_used.append(tool_call.name)
                        result = await self_loop.tools.execute(tool_call.name, tool_call.arguments)
                        messages = self_loop.context.add_tool_result(
                            messages, tool_call.id, tool_call.name, result
                        )
                        # CHECKPOINT: After Tool Result
                        await _checkpoint_step(messages, iteration)
                else:
                    clean = self_loop._strip_think(response.content)
                    if response.finish_reason == "error":
                        final_content = clean or "Sorry, I encountered an error."
                        break
                    messages = self_loop.context.add_assistant_message(
                        messages, clean, reasoning_content=response.reasoning_content,
                        thinking_blocks=response.thinking_blocks,
                    )
                    final_content = clean
                    # FINAL CHECKPOINT
                    await _checkpoint_step(messages, iteration + 1)
                    break

            if final_content is None and iteration >= self_loop.max_iterations:
                final_content = f"I reached the maximum number of iterations ({self_loop.max_iterations})."

            return final_content, tools_used, messages

        AgentLoop._run_agent_loop = patched_run_loop

    def _patch_subagent_manager(self, manager, context: PatchContext):
        from nanobot.agent.subagent import SubagentManager

        async def patched_run_subagent(self_sub, task_id, task, label, origin, *args, **kwargs):
            try:
                # Resolve specialist, host_tools, attachments from args/kwargs if present
                # SubagentPatch passes: (task_id, task, label, origin, specialist, host_tools, attachments)
                specialist = kwargs.get("specialist", args[0] if len(args) > 0 else "researcher")
                host_tools = kwargs.get("host_tools", args[1] if len(args) > 1 else None)
                attachments = kwargs.get("attachments", args[2] if len(args) > 2 else None)

                # MANDATE (BUG-223): Use strategic model routing
                final_model = subagent_logic.get_specialist_model(specialist, context.config, self_sub.model)

                thread_id = f"subagent:{task_id}"
                manager.create_thread(thread_id, final_model, {"label": label, "task": task, "origin": origin, "specialist": specialist})

                logger.info("Subagent [{}] starting DURABLE task: {} using model {}", task_id, label, final_model)

                # BUG-253: Logic Isolation & Resource Leak.
                # We must ensure MCP tools are bridged efficiently.
                async with AsyncExitStack() as stack:
                    from nanobot.agent.tools.filesystem import (
                        EditFileTool,
                        ListDirTool,
                        ReadFileTool,
                        WriteFileTool,
                    )
                    from nanobot.agent.tools.registry import ToolRegistry
                    from nanobot.agent.tools.shell import ExecTool
                    from nanobot.agent.tools.web import WebFetchTool, WebSearchTool

                    from .vsa import VectorStoreFactory

                    tools = ToolRegistry()
                    tools._is_strategic_specialist = True
                    tools._task_id = task_id

                    # Warm up Vector Store
                    VectorStoreFactory.get_store(provider=self_sub.provider)
                    allowed_dir = self_sub.workspace if self_sub.restrict_to_workspace else None
                    tools.register(ReadFileTool(workspace=self_sub.workspace, allowed_dir=allowed_dir))
                    tools.register(WriteFileTool(workspace=self_sub.workspace, allowed_dir=allowed_dir))
                    tools.register(EditFileTool(workspace=self_sub.workspace, allowed_dir=allowed_dir))
                    tools.register(ListDirTool(workspace=self_sub.workspace, allowed_dir=allowed_dir))
                    tools.register(ExecTool(
                        working_dir=str(self_sub.workspace),
                        timeout=max(self_sub.exec_config.timeout, 300),
                        restrict_to_workspace=self_sub.restrict_to_workspace,
                        path_append=self_sub.exec_config.path_append,
                    ))
                    tools.register(WebSearchTool(api_key=self_sub.brave_api_key, proxy=self_sub.web_proxy))
                    tools.register(WebFetchTool(proxy=self_sub.web_proxy))

                    # BUG-235: Bridge host tools and MCP servers
                    await subagent_logic.bridge_subagent_tools(tools, host_tools, context.config, stack.enter_async_context)

                    # Load Strategic Tools (Multimodal, etc)
                    from strategery.patches.subagent import SubagentPatch
                    sp = SubagentPatch()
                    sp._load_strategic_tools(tools, model=final_model)

                    # Use Strategic Instructions (BUG-223)
                    system_prompt = subagent_logic.build_specialist_instructions(self_sub._build_subagent_prompt(), specialist, attachments)

                    messages: list[dict[str, Any]] = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": task},
                    ]

                    # BUG-252: Delegate to durable orchestration loop with checkpointing
                    async def _checkpoint_provider_wrapper(messages, tools, model, temperature, max_tokens, reasoning_effort):
                        # Save snapshot before each chat turn
                        current_it = (len([m for m in messages if m["role"] == "assistant"]) + 1)
                        manager.save_snapshot(thread_id, current_it, messages)

                        resp = await self_sub.provider.chat(
                            messages=messages,
                            tools=tools,
                            model=model,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            reasoning_effort=reasoning_effort
                        )
                        return resp

                    # We patch the execute method of tools to inject checkpoints after each call
                    orig_tools_execute = tools.execute
                    async def _patched_tools_execute(name, arguments):
                        res = await orig_tools_execute(name, arguments)
                        # Save snapshot after each tool result
                        current_it = (len([m for m in messages if m["role"] == "assistant"]))
                        manager.save_snapshot(thread_id, current_it, messages)
                        return res
                    tools.execute = _patched_tools_execute

                    # Wrap the provider to use our checkpointing logic
                    provider_proxy = type('ProviderProxy', (), {
                        'chat': _checkpoint_provider_wrapper
                    })

                    final_result = await subagent_logic.run_orchestration_loop(
                        task_id=task_id,
                        task=task,
                        messages=messages,
                        provider=provider_proxy,
                        model=final_model,
                        tools=tools,
                        temperature=self_sub.temperature,
                        max_tokens=self_sub.max_tokens,
                        reasoning_effort=self_sub.reasoning_effort
                    )

                manager.save_snapshot(thread_id, 99, messages) # Final State
                manager.complete_thread(thread_id)
                logger.info("Subagent [{}] completed successfully", task_id)
                await self_sub._announce_result(task_id, label, task, final_result, origin, "ok")

            except Exception as e:
                import traceback
                error_msg = f"Error: {str(e)}"
                logger.error("Subagent [{}] failed: {}\n{}", task_id, e, traceback.format_exc())
                await self_sub._announce_result(task_id, label, task, error_msg, origin, "error")

        SubagentManager._run_subagent = patched_run_subagent

        SubagentManager._run_subagent = patched_run_subagent

    def _patch_process_message(self, manager, context: PatchContext):
        from nanobot.agent.loop import AgentLoop
        original_process = AgentLoop._process_message

        @functools.wraps(original_process)
        async def patched_process(self_loop, msg, **kwargs):
            thread_id = f"session:{msg.session_key}"
            self_loop._current_thread_id = thread_id
            manager.create_thread(thread_id, self_loop.model, {"channel": msg.channel, "chat_id": msg.chat_id})

            result = await original_process(self_loop, msg, **kwargs)
            # If successfully finished, we could mark as complete, but chat sessions are persistent.
            return result

        AgentLoop._process_message = patched_process
