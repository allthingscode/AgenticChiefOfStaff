import asyncio
import json
import weakref
from .base import BasePatch
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

    def apply(self, config: dict) -> bool:
        # 1. Patch __init__ to initialize our strategic lock dictionary
        if not hasattr(AgentLoop, "_orig_init_strategic"):
            AgentLoop._orig_init_strategic = AgentLoop.__init__
            
            def _patched_init(self, *args, **kwargs):
                self._orig_init_strategic(*args, **kwargs)
                # Initialize per-session lock dictionary on the instance
                self._strategic_session_locks = weakref.WeakValueDictionary()
                
            AgentLoop.__init__ = _patched_init
            logger.debug("Patched AgentLoop.__init__ for per-session locking")

        # 2. Patch _dispatch to use the per-session lock
        if not hasattr(AgentLoop, "_orig_dispatch_strategic"):
            AgentLoop._orig_dispatch_strategic = AgentLoop._dispatch
            
            async def _patched_dispatch(self, msg):
                """Process a message under a per-session lock instead of global lock."""
                # Initialize session locks if they don't exist (for instances created before patch)
                if not hasattr(self, "_strategic_session_locks"):
                    self._strategic_session_locks = weakref.WeakValueDictionary()

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
            
        return True
