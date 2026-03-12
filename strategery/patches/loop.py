import asyncio
import json
import weakref
from typing import List
from .base import BasePatch, PatchResult, PatchContext
from nanobot.agent.loop import AgentLoop
from nanobot.bus.events import OutboundMessage
from loguru import logger

class AgentLoopPatch(BasePatch):
    """
    Hardens the Agent Loop by:
    1. Replacing the global '_processing_lock' with per-session locks to enable
       concurrency across different users/channels while maintaining order per session.
    2. Using a WeakValueDictionary to ensure locks are garbage collected when inactive.
    """

    @property
    def name(self) -> str:
        return "Agent Loop (Concurrent Sessions)"

    @property
    def required_symbols(self) -> List[str]:
        return [
            "nanobot.agent.loop.AgentLoop._dispatch",
            "nanobot.agent.loop.AgentLoop._run_agent_loop",
            "nanobot.bus.events.OutboundMessage"
        ]

    def apply(self, context: PatchContext) -> PatchResult:
        result = PatchResult(patch_name=self.name, success=True)
        try:
            # 1. Patch __init__ to initialize our strategic lock dictionary
            if not hasattr(AgentLoop, "_orig_init_strategic"):
                AgentLoop._orig_init_strategic = AgentLoop.__init__
                
                def _patched_init(self, *args, **kwargs):
                    self._orig_init_strategic(*args, **kwargs)
                    # Initialize per-session lock dictionary and subagent registry
                    self._strategic_session_locks = weakref.WeakValueDictionary()
                    self._strategic_active_subagents = {} # Map[ID, {'start_time': datetime, 'task': str}]
                    self._strategic_monitor_task = None

                async def _strategic_monitor_subagents(self):
                    """Background task to warn of 'Ghost' subagents that hang indefinitely."""
                    from datetime import datetime
                    while True:
                        await asyncio.sleep(60) # Check every minute
                        now = datetime.now()
                        to_remove = []
                        for sid, info in self._strategic_active_subagents.items():
                            diff = (now - info['start_time']).total_seconds()
                            if diff > 600: # 10 minutes (Threshold for 'Ghosting')
                                logger.warning("STRATEGIC ALERT: Subagent [{}] has been running for {}s. Task: {}", sid, int(diff), info['task'][:50])
                            # If extremely long (e.g. 1 hour), consider it dead
                            if diff > 3600:
                                to_remove.append(sid)

                        for sid in to_remove:
                            del self._strategic_active_subagents[sid]

                AgentLoop._strategic_monitor_subagents = _strategic_monitor_subagents
                AgentLoop.__init__ = _patched_init
                logger.debug("Patched AgentLoop.__init__ for per-session locking")
                result.affected_symbols.append("AgentLoop.__init__")

            # 2. Patch _dispatch to use the per-session lock
            if not hasattr(AgentLoop, "_orig_dispatch_strategic"):
                AgentLoop._orig_dispatch_strategic = AgentLoop._dispatch
                
                async def _patched_dispatch(self, msg):
                    """Process a message under a per-session lock instead of global lock."""
                    # Initialize session locks if they don't exist (for instances created before patch)
                    if not hasattr(self, "_strategic_session_locks"):
                        self._strategic_session_locks = weakref.WeakValueDictionary()

                    # Lazily start the heartbeat monitor task (BUG-104 fix)
                    if not getattr(self, "_strategic_monitor_task", None):
                        self._strategic_monitor_task = asyncio.create_task(self._strategic_monitor_subagents())

                    # STRATEGIC: Strip [SILENT] prefix if present to keep the prompt clean for the agent
                    # This prefix is used by cron_logic to suppress routing, but the agent shouldn't see it.
                    if msg.content and msg.content.startswith("[SILENT]"):
                        msg.content = msg.content.replace("[SILENT]", "", 1).strip()

                    session_key = msg.session_key

                    lock = self._strategic_session_locks.get(session_key)
                    if lock is None:
                        lock = asyncio.Lock()
                        self._strategic_session_locks[session_key] = lock
                    
                    async with lock:
                        # We still want to call the internal _process_message but WITHOUT the global lock
                        # The original _dispatch used the global lock. 
                        # We call the CURRENT _process_message (which might be patched by others)
                        try:
                            response = await self._process_message(msg)
                            if response is not None:
                                await self.bus.publish_outbound(response)
                            elif msg.channel == "cli":
                                await self.bus.publish_outbound(OutboundMessage(
                                    channel=msg.channel, chat_id=msg.chat_id,
                                    content="", metadata=msg.metadata or {},
                                ))
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            logger.exception("Error processing message for session {}", msg.session_key)
                            await self.bus.publish_outbound(OutboundMessage(
                                channel=msg.channel, chat_id=msg.chat_id,
                                content="Sorry, I encountered an error.",
                            ))
                
                AgentLoop._dispatch = _patched_dispatch
                logger.debug("Patched AgentLoop._dispatch for per-session locking")
                result.affected_symbols.append("AgentLoop._dispatch")
                
            # 3. Patch _run_agent_loop to implement "Silent Spawn" (BUG-111)
            if not hasattr(AgentLoop, "_orig_run_agent_loop_strategic"):
                AgentLoop._orig_run_agent_loop_strategic = AgentLoop._run_agent_loop
                
                async def _patched_run_agent_loop(self, initial_messages, on_progress=None):
                    """Strategic override of _run_agent_loop to prevent ID hallucination."""
                    from typing import Callable, Awaitable
                    import json
                    from loguru import logger
                    
                    messages = initial_messages
                    iteration = 0
                    final_content = None
                    tools_used: list[str] = []

                    while iteration < self.max_iterations:
                        iteration += 1

                        response = await self.provider.chat(
                            messages=messages,
                            tools=self.tools.get_definitions(),
                            model=self.model,
                            temperature=self.temperature,
                            max_tokens=self.max_tokens,
                            reasoning_effort=self.reasoning_effort,
                        )

                        if response.has_tool_calls:
                            # STRATEGIC: Detect 'spawn' call (BUG-110/111)
                            is_spawn = any(tc.name == "spawn" for tc in response.tool_calls)
                            
                            if on_progress:
                                # If it's a spawn, we SUPPRESS the thought/hint entirely.
                                # The user will only see the final acknowledgement after the tool returns.
                                if not is_spawn:
                                    thought = self._strip_think(response.content)
                                    if thought:
                                        # Log thought process strategically (F-015 high-fidelity)
                                        from strategery.logic import subagent_logic
                                        # We simulate a 'turn' log for the main agent
                                        subagent_logic.log_subagent_turn("MAIN", iteration, response.content)
                                        await on_progress(thought)
                                    await on_progress(self._tool_hint(response.tool_calls), tool_hint=True)
                                else:
                                    logger.debug("Silent Spawn: Suppressing progress content for subagent creation to prevent hallucination.")

                            tool_call_dicts = [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.name,
                                        "arguments": json.dumps(tc.arguments, ensure_ascii=False)
                                    }
                                }
                                for tc in response.tool_calls
                            ]
                            messages = self.context.add_assistant_message(
                                messages, response.content, tool_call_dicts,
                                reasoning_content=response.reasoning_content,
                                thinking_blocks=response.thinking_blocks,
                            )

                            for tool_call in response.tool_calls:
                                tools_used.append(tool_call.name)
                                result = await self.tools.execute(tool_call.name, tool_call.arguments)
                                messages = self.context.add_tool_result(
                                    messages, tool_call.id, tool_call.name, result
                                )
                        else:
                            clean = self._strip_think(response.content)
                            if response.finish_reason == "error":
                                logger.error("LLM returned error: {}", (clean or "")[:200])
                                final_content = clean or "Sorry, I encountered an error calling the AI model."
                                break
                            messages = self.context.add_assistant_message(
                                messages, clean, reasoning_content=response.reasoning_content,
                                thinking_blocks=response.thinking_blocks,
                            )
                            final_content = clean
                            break

                    if final_content is None and iteration >= self.max_iterations:
                        logger.warning("Max iterations ({}) reached", self.max_iterations)
                        final_content = (
                            f"I reached the maximum number of tool call iterations ({self.max_iterations}) "
                            "without completing the task. You can try breaking the task into smaller steps."
                        )

                    return final_content, tools_used, messages

                AgentLoop._run_agent_loop = _patched_run_agent_loop
                logger.debug("Patched AgentLoop._run_agent_loop for 'Silent Spawn' (BUG-111)")
                result.affected_symbols.append("AgentLoop._run_agent_loop")

            return result
        except Exception as e:
            import traceback
            result.success = False
            result.error_msg = str(e)
            result.traceback = traceback.format_exc()
            logger.error(f"AgentLoop patch error: {e}")
            return result

    def verify(self, config: dict) -> bool:
        """Verifies that the AgentLoop class and instances are correctly patched."""
        # 1. Check class-level patches
        if not hasattr(AgentLoop, "_orig_init_strategic"):
            return False
        if not hasattr(AgentLoop, "_strategic_monitor_subagents"):
            return False
        if not hasattr(AgentLoop, "_orig_dispatch_strategic"):
            return False
        if not hasattr(AgentLoop, "_orig_run_agent_loop_strategic"):
            return False
        
        return True
